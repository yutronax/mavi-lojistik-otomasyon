# -*- coding: utf-8 -*-
"""API Key Manager

Encapsulates collection, rotation, and application of API keys.
This is designed to replace the global key-handling logic in veri_cekici_ayristirici.py
and make testing/refactoring easier.
"""

import os
import importlib
import sys
import time
import re
from typing import List, Optional
import logging
import asyncio
logger = logging.getLogger(__name__)


class APIKeyManager:
    def __init__(self, root_dir: Optional[str] = None):
        self._keys: List[str] = []
        self._active_index: int = -1
        self._exhausted = set()
        self._last_check_time: float = 0.0
        self.root_dir = root_dir
        self._lock = asyncio.Lock()

    import re

    def _parse_api_keys_from_string(self, value: str) -> List[str]:
        """Split a string into API keys using commas or whitespace as separators."""
        if not value:
            return []
        parts = re.split(r'[,\s]+', value)
        return [p.strip() for p in parts if p.strip()]

    def _collect_from_env(self) -> List[str]:
        keys: List[str] = []
        # Groq keys (primary - new system)
        groq_multi = os.getenv('GROQ_API_KEYS')
        if groq_multi:
            keys.extend(self._parse_api_keys_from_string(groq_multi))
        groq_single = os.getenv('GROQ_API_KEY')
        if groq_single:
            keys.append(groq_single.strip())
        # Legacy Gemini keys (fallback)
        multi_env = os.getenv('GEMINI_API_KEYS') or os.getenv('GOOGLE_API_KEYS')
        if multi_env:
            keys.extend(self._parse_api_keys_from_string(multi_env))
        single_env = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if single_env:
            keys.append(single_env.strip())
        return keys

    def _collect_from_config(self) -> List[str]:
        keys = []
        if not self.root_dir:
            return keys
        config_path = os.path.join(self.root_dir, 'config_api_key.py')
        if not os.path.exists(config_path):
            return keys
        module_name = 'config_api_key'
        try:
            # ensure importability
            if self.root_dir not in sys.path:
                sys.path.insert(0, self.root_dir)
            if module_name in sys.modules:
                importlib.reload(sys.modules[module_name])
            else:
                importlib.import_module(module_name)
            mod = sys.modules.get(module_name)
            if not mod:
                return keys
            if hasattr(mod, 'API_KEYS'):
                config_keys = [k.strip() for k in getattr(mod, 'API_KEYS') if k]
                keys.extend(config_keys)
            elif hasattr(mod, 'API_KEY'):
                ck = str(getattr(mod, 'API_KEY')).strip()
                if ck:
                    keys.append(ck)
        except Exception:
            # Non-fatal; return what we have
            return keys
        return keys

    def load_keys(self, force_reload: bool = False, reason: str = "initial") -> bool:
        if self._keys and not force_reload:
            return True
        keys: List[str] = []
        keys.extend(self._collect_from_env())
        keys.extend(self._collect_from_config())
        # dedupe preserve order
        seen = set()
        deduped = []
        for k in keys:
            nk = str(k).strip()
            if nk and nk not in seen:
                seen.add(nk)
                deduped.append(nk)
        self._keys = deduped
        self._last_check_time = time.time()
        if not self._keys:
            return False
        # select first non-exhausted
        for idx, k in enumerate(self._keys):
            if k not in self._exhausted:
                self._active_index = idx
                self.apply_key(k, announce=True, reason=reason)
                return True
        # none available
        return False

    def get_active_key(self) -> Optional[str]:
        if 0 <= self._active_index < len(self._keys):
            return self._keys[self._active_index]
        return None

    def get_all_keys(self) -> List[str]:
        return list(self._keys)

    def get_active_index(self) -> int:
        return int(self._active_index)

    def apply_key(self, key: str, announce: bool = True, reason: str = ""):
        os.environ['GOOGLE_API_KEY'] = key
        os.environ['GEMINI_API_KEY'] = key
        if announce:
            masked = key[:6] + '...' + key[-4:] if key and len(key) > 10 else key
            total = len(self._keys) or 1
            index = self._active_index + 1 if self._active_index >= 0 else 1
            reason_text = f" ({reason})" if reason else ""
            logger.debug(f"[] API key #{index}/{total} aktif: {masked}{reason_text}")

    async def switch_to_next_async(self, reason: str = "") -> bool:
        """Asynchronous version of switch_to_next with locking."""
        async with self._lock:
            if not self._keys:
                if not self.load_keys(force_reload=True, reason=reason or 'reload'):
                    return False
            
            if 0 <= self._active_index < len(self._keys):
                self._exhausted.add(self._keys[self._active_index])
            
            # find next non-exhausted
            for idx in range(self._active_index + 1, len(self._keys)):
                if self._keys[idx] not in self._exhausted:
                    self._active_index = idx
                    self.apply_key(self._keys[self._active_index], announce=True, reason=reason or 'quota limit')
                    return True
            
            # try reloading and selecting again
            if self.load_keys(force_reload=True, reason=reason or 'reload'):
                if 0 <= self._active_index < len(self._keys):
                    current = self._keys[self._active_index]
                    if current not in self._exhausted:
                        return True
            return False

    def switch_to_next(self, reason: str = "") -> bool:
        # Keep sync version for compatibility, but note it's not lock-protected for async
        if not self._keys:
            if not self.load_keys(force_reload=True, reason=reason or 'reload'):
                return False
        if 0 <= self._active_index < len(self._keys):
            self._exhausted.add(self._keys[self._active_index])
        # find next non-exhausted
        for idx in range(self._active_index + 1, len(self._keys)):
            if self._keys[idx] not in self._exhausted:
                self._active_index = idx
                self.apply_key(self._keys[self._active_index], announce=True, reason=reason or 'quota limit')
                return True
        # try reloading and selecting again
        if self.load_keys(force_reload=True, reason=reason or 'reload'):
            if 0 <= self._active_index < len(self._keys):
                current = self._keys[self._active_index]
                if current not in self._exhausted:
                    return True
        return False

    def mark_exhausted(self, key: str):
        if key:
            self._exhausted.add(key)

    def all_exhausted(self) -> bool:
        return all(k in self._exhausted for k in self._keys)


# Singleton default manager used by the codebase (can be replaced in tests)
_default_manager: Optional[APIKeyManager] = None


def get_default_manager(root_dir: Optional[str] = None) -> APIKeyManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = APIKeyManager(root_dir=root_dir)
        _default_manager.load_keys(reason='manager_lazy_init')
    return _default_manager
