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
        self._google_keys: List[str] = []
        self._groq_keys: List[str] = []
        
        self._google_index: int = -1
        self._groq_index: int = -1
        
        # Exhausted keys: {key: timestamp_of_exhaustion}
        self._exhausted_stats: Dict[str, float] = {}
        self.root_dir = root_dir
        self._lock = asyncio.Lock()
        self.cooldown_seconds = 61 # Gemini limits are per minute

    def _parse_api_keys_from_string(self, value: str) -> List[str]:
        if not value: return []
        parts = re.split(r'[,\s]+', value)
        return [p.strip() for p in parts if p.strip()]

    def _collect_from_env(self) -> List[str]:
        keys = []
        # Groq keys
        groq_multi = os.getenv('GROQ_API_KEYS')
        if groq_multi: keys.extend(self._parse_api_keys_from_string(groq_multi))
        groq_single = os.getenv('GROQ_API_KEY')
        if groq_single: keys.append(groq_single.strip())
        
        # Google/Gemini keys
        gemini_multi = os.getenv('GEMINI_API_KEYS') or os.getenv('GOOGLE_API_KEYS')
        if gemini_multi: keys.extend(self._parse_api_keys_from_string(gemini_multi))
        gemini_single = os.getenv('GOOGLE_API_KEY') or os.getenv('GEMINI_API_KEY')
        if gemini_single: keys.append(gemini_single.strip())
        return keys

    def load_keys(self, force_reload: bool = False, reason: str = "initial") -> bool:
        all_keys = self._collect_from_env()
        
        google_new = []
        groq_new = []
        seen = set()
        
        for k in all_keys:
            if k in seen: continue
            seen.add(k)
            if k.startswith('gsk_'):
                groq_new.append(k)
            elif k.startswith('AIza'):
                google_new.append(k)

        self._google_keys = google_new
        self._groq_keys = groq_new
        
        # Reset indices to first available
        if self._google_keys and self._google_index == -1:
            self._google_index = 0
            self.apply_key(self._google_keys[0], announce=True, reason=reason)
            
        if self._groq_keys and self._groq_index == -1:
            self._groq_index = 0
            self.apply_key(self._groq_keys[0], announce=True, reason=reason)
            
        return len(self._google_keys) + len(self._groq_keys) > 0

    def get_wait_time(self, key_type: str = 'google') -> float:
        """Returns seconds to wait until the oldest exhausted key might be available."""
        keys = self._google_keys if key_type == 'google' else self._groq_keys
        if not keys: return 0
        
        now = time.time()
        wait_times = []
        
        for k in keys:
            if k in self._exhausted_stats:
                elapsed = now - self._exhausted_stats[k]
                remaining = self.cooldown_seconds - elapsed
                if remaining > 0:
                    wait_times.append(remaining)
                else:
                    # Key is actually ready!
                    return 0
            else:
                # One key is already ready
                return 0
        
        return min(wait_times) if wait_times else 0

    def get_active_key(self, key_type: str = 'google') -> Optional[str]:
        if key_type == 'google':
            if 0 <= self._google_index < len(self._google_keys):
                return self._google_keys[self._google_index]
        else:
            if 0 <= self._groq_index < len(self._groq_keys):
                return self._groq_keys[self._groq_index]
        return None

    def get_all_keys(self) -> List[str]:
        """Returns all keys from both pools for legacy support."""
        return self._google_keys + self._groq_keys

    def get_active_index(self) -> int:
        """Returns the google index as the 'primary' active index for legacy support."""
        return self._google_index

    def apply_key(self, key: str, announce: bool = True, reason: str = ""):
        is_groq = key.startswith('gsk_')
        is_google = key.startswith('AIza')

        if is_groq:
            os.environ['GROQ_API_KEY'] = key
        elif is_google:
            os.environ['GOOGLE_API_KEY'] = key
            os.environ['GEMINI_API_KEY'] = key

        if announce:
            masked = key[:6] + '...' + key[-4:] if len(key) > 10 else key
            k_type = "GOOGLE" if is_google else "GROQ"
            pool_size = len(self._google_keys) if is_google else len(self._groq_keys)
            idx = (self._google_index if is_google else self._groq_index) + 1
            logger.info(f"🔑 API Key switched: {k_type} #{idx}/{pool_size} [{masked}] Reason: {reason}")

    async def switch_to_next_async(self, key_type: str = 'google', reason: str = "") -> bool:
        """Rotates key for a specific pool (google or groq). Handles cooldown recovery."""
        async with self._lock:
            keys = self._google_keys if key_type == 'google' else self._groq_keys
            idx = self._google_index if key_type == 'google' else self._groq_index
            
            if not keys: return False
            
            now = time.time()
            # Mark current as exhausted with timestamp
            if 0 <= idx < len(keys):
                self._exhausted_stats[keys[idx]] = now
            
            # 1. Search for a fresh key or a cooled-down one
            for i in range(len(keys)):
                k = keys[i]
                # Is it fresh or cooled down?
                is_ready = False
                if k not in self._exhausted_stats:
                    is_ready = True
                else:
                    elapsed = now - self._exhausted_stats[k]
                    if elapsed >= self.cooldown_seconds:
                        is_ready = True
                        del self._exhausted_stats[k] # Recovered!
                
                if is_ready:
                    if key_type == 'google': self._google_index = i
                    else: self._groq_index = i
                    self.apply_key(k, announce=True, reason=reason)
                    return True
            
            return False

    def mark_exhausted(self, key: str):
        self._exhausted_stats[key] = time.time()

    def all_exhausted(self) -> bool:
        # Check all keys if they are currently in cooldown
        now = time.time()
        for k in self._google_keys + self._groq_keys:
            if k not in self._exhausted_stats: return False
            if now - self._exhausted_stats[k] >= self.cooldown_seconds: return False
        return True


# Singleton default manager used by the codebase (can be replaced in tests)
_default_manager: Optional[APIKeyManager] = None


def get_default_manager(root_dir: Optional[str] = None) -> APIKeyManager:
    global _default_manager
    if _default_manager is None:
        _default_manager = APIKeyManager(root_dir=root_dir)
        _default_manager.load_keys(reason='manager_lazy_init')
    return _default_manager
