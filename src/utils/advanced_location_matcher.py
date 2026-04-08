# -*- coding: utf-8 -*-
"""
advanced_location_matcher.py - Gelişmiş il/ilçe eşleştirme sistemi

Bu modül `il_ilçeler.json` dosyasını kullanarak önce il (şehir),
sonra ilçe eşleştirmesi yapar. Eğer verilen `il` JSON içindeki iller
arasinda bulunuyorsa o il kabul edilir; il yoksa verilen `ilçe`
isimlerinden biri bulunup bulunmadığı kontrol edilir ve bulunduğu il
atanır. JSON'da olmayan kelimeler asla il/ilçe olarak yazılmaz (boş
olarak bırakılır).
# -*- coding: utf-8 -*-

advanced_location_matcher.py - Gelişmiş il/ilçe eşleştirme sistemi

Bu modül `il_ilçeler.json` dosyasını kullanarak önce il (şehir), sonra ilçe
eşleştirmesi yapar. Eğer verilen `il` JSON içindeki iller arasında bulunuyorsa o
il kabul edilir; il yoksa verilen `ilçe` isimlerinden biri bulunup bulunmadığı
kontrol edilir ve bulunduğu il atanır. JSON'da olmayan kelimeler asla il/ilçe
olarak yazılmaz (boş olarak bırakılır).
"""

from pathlib import Path
# -*- coding: utf-8 -*-
"""
advanced_location_matcher.py - Gelişmiş il/ilçe eşleştirme sistemi

Bu modül `il_ilçeler.json` dosyasını kullanarak önce il (şehir), sonra ilçe
eşleştirmesi yapar. Eğer verilen `il` JSON içindeki iller arasında bulunuyorsa o
il kabul edilir; il yoksa verilen `ilçe` isimlerinden biri bulunup bulunmadığı
kontrol edilir ve bulunduğu il atanır. JSON'da olmayan kelimeler asla il/ilçe
olarak yazılmaz (boş olarak bırakılır).
"""

from pathlib import Path
import json
import os
from typing import Optional
import unicodedata

# Optional AI Location Validator for web search fallback
try:
    from ai_location_validator import AILocationValidator
    AI_VALIDATOR_AVAILABLE = True
except Exception:
    AI_VALIDATOR_AVAILABLE = False
    AILocationValidator = None


def _normalize(s: Optional[str]) -> str:
    if not s:
        return ''
    import re
    text = s.strip().upper()
    text = re.sub(r"[^A-ZÖÜÇĞŞİ\s0-9]", '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _normalize_nospace(s: Optional[str]) -> str:
    if not s:
        return ''
    return ''.join(s.strip().upper().split())


def _asciifold_nospace(s: Optional[str]) -> str:
    if not s:
        return ''
    nk = unicodedata.normalize('NFKD', s)
    folded = ''.join(ch for ch in nk if ord(ch) < 128)
    return ''.join(folded.strip().upper().split())


def _normalize_token(s: Optional[str]) -> str:
    if not s:
        return ''
    import re
    text = s.strip().upper()
    text = re.sub(r"[^A-ZÖÜÇĞŞİ\s0-9]", '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


class LocationMatcher:
    def __init__(self, il_ilce_data: Optional[list] = None):
        # If a path string or Path is supplied, load JSON from that path
        if isinstance(il_ilce_data, (str, Path)):
            candidate = Path(il_ilce_data)
            try:
                with open(candidate, 'r', encoding='utf-8') as f:
                    il_ilce_data = json.load(f)
            except Exception:
                il_ilce_data = []

        if il_ilce_data is None:
            base = Path(__file__).resolve().parent.parent
            # Try several candidate paths to find the data file (project data/ dir, package dir, cwd)
            candidates = [
                base / 'il_ilçeler.json',
                base / 'data' / 'il_ilçeler.json',
                Path(os.getcwd()) / 'il_ilçeler.json',
                Path(os.getcwd()) / 'data' / 'il_ilçeler.json',
            ]
            found = False
            for candidate in candidates:
                try:
                    if candidate.exists():
                        with open(candidate, 'r', encoding='utf-8') as f:
                            il_ilce_data = json.load(f)
                        found = True
                        break
                except Exception:
                    continue
            if not found:
                il_ilce_data = []

        self.raw = il_ilce_data or []
        self.il_to_ilceler = {}
        self.ilce_to_il = {}
        self.il_original = {}
        self.ilce_original = {}
        self.default_ilce = {}

        for entry in self.raw:
            il_name = entry.get('il', '')
            il_key = _normalize(il_name)
            il_key_nos = _normalize_nospace(il_name)
            il_key_asci = _asciifold_nospace(il_name)

            if il_key:
                self.il_original[il_key] = il_name
            if il_key_nos:
                self.il_original[il_key_nos] = il_name
            if il_key_asci:
                self.il_original[il_key_asci] = il_name

            ilceler = entry.get('ilçe', []) or []
            ilce_keys = set()
            ilce_asci_keys = set()
            for ic in ilceler:
                k1 = _normalize(ic)
                k2 = _normalize_nospace(ic)
                k3 = _asciifold_nospace(ic)
                if k1:
                    ilce_keys.add(k1)
                if k2:
                    ilce_keys.add(k2)
                if k3:
                    ilce_keys.add(k3)
                    ilce_asci_keys.add(k3)

                if k1:
                    self.ilce_original[(k1, il_key)] = ic
                    self.ilce_to_il[k1] = il_key
                if k2:
                    self.ilce_original[(k2, il_key)] = ic
                    self.ilce_to_il[k2] = il_key
                if k3:
                    self.ilce_original[(k3, il_key)] = ic
                    self.ilce_to_il[k3] = il_key

            if il_key:
                self.il_to_ilceler[il_key] = ilce_keys
            if il_key_nos:
                self.il_to_ilceler[il_key_nos] = ilce_keys
            if il_key_asci:
                self.il_to_ilceler[il_key_asci] = ilce_keys.union(ilce_asci_keys)

            default = entry.get('varsayılan_ilçe') or ''
            if default:
                if il_key:
                    self.default_ilce[il_key] = default
                if il_key_nos:
                    self.default_ilce[il_key_nos] = default
                if il_key_asci:
                    self.default_ilce[il_key_asci] = default

    def _get_default_ilce(self, key_il: str, context_text: str) -> str:
        default = self.default_ilce.get(key_il, '')
        if key_il == 'İSTANBUL' or key_il == 'ISTANBUL':
            ctx = context_text.upper()
            if 'AVRUPA' in ctx:
                return 'Avcılar'
            else:
                return 'Maltepe'
        return default

    def validate_and_fix(self, il: Optional[str], ilce: Optional[str], location_text: str = '') -> dict:
        il_in = _normalize(il)
        il_in_nos = _normalize_nospace(il)
        il_in_asci = _asciifold_nospace(il)
        ilce_in = _normalize(ilce)
        ilce_in_nos = _normalize_nospace(ilce)
        ilce_in_asci = _asciifold_nospace(ilce)
        
        # Eğer il/ilçe stringleri tam eşleşmezse token ayrıştırıcıya da girmesini sağlamak için metinleri birleştir.
        combined_ctx = f"{il or ''} {ilce or ''} {location_text}"
        text = _normalize(combined_ctx)

        if il_in and (il_in in self.il_to_ilceler or il_in_nos in self.il_to_ilceler or il_in_asci in self.il_to_ilceler):
            key_il = il_in if il_in in self.il_to_ilceler else (il_in_nos if il_in_nos in self.il_to_ilceler else il_in_asci)
            result_il = self.il_original.get(key_il, key_il.title())
            if ilce_in and (ilce_in in self.il_to_ilceler.get(key_il, set()) or ilce_in_nos in self.il_to_ilceler.get(key_il, set()) or ilce_in_asci in self.il_to_ilceler.get(key_il, set())):
                chosen = ilce_in if ilce_in in self.il_to_ilceler.get(key_il, set()) else (ilce_in_nos if ilce_in_nos in self.il_to_ilceler.get(key_il, set()) else ilce_in_asci)
                result_ilce = self.ilce_original.get((chosen, key_il), ilce)
                confidence = 0.95
            else:
                default = self._get_default_ilce(key_il, combined_ctx)
                if default:
                    result_ilce = default
                    confidence = 0.9
                else:
                    result_ilce = ''
                    confidence = 0.6
            return {'il': result_il, 'ilce': result_ilce, 'confidence': confidence, 'needs_gemini': False}

        if ilce_in:
            ilce_cands = [ilce_in, ilce_in_nos, ilce_in_asci]
            for cand in ilce_cands:
                if cand and cand in self.ilce_to_il:
                    mapped_il_upper = self.ilce_to_il[cand]
                    result_il = self.il_original.get(mapped_il_upper, mapped_il_upper.title())
                    result_ilce = self.ilce_original.get((cand, mapped_il_upper), ilce)
                    confidence = 0.95
                    return {'il': result_il, 'ilce': result_ilce, 'confidence': confidence, 'needs_gemini': False}

        tokens = [t for t in text.replace(',', ' ').split() if t]
        n = len(tokens)
        for i in range(n):
            for j in range(i + 1, min(i + 4, n + 1)):
                chunk_space = ' '.join(tokens[i:j])
                chunk_nospace = ''.join(tokens[i:j])
                chunk_asci = _asciifold_nospace(chunk_space)
                chunk_space_cleaned = _normalize_token(chunk_space)
                chunk_nospace_cleaned = _normalize_token(chunk_nospace)
                chunk_asci_cleaned = _asciifold_nospace(chunk_space_cleaned)

                for chunk, original in [
                    (chunk_space, chunk_space),
                    (chunk_nospace, chunk_nospace),
                    (chunk_asci, chunk_asci),
                    (chunk_space_cleaned, chunk_space_cleaned),
                    (chunk_nospace_cleaned, chunk_nospace_cleaned),
                    (chunk_asci_cleaned, chunk_asci_cleaned),
                ]:
                    if chunk in self.il_to_ilceler:
                        result_il = self.il_original.get(chunk, original.title())
                        result_ilce = self._get_default_ilce(chunk, text)
                        confidence = 0.9
                        return {'il': result_il, 'ilce': result_ilce or '', 'confidence': confidence, 'needs_gemini': False}

                    if chunk in self.ilce_to_il:
                        mapped = self.ilce_to_il.get(chunk)
                        if mapped:
                            result_il = self.il_original.get(mapped, mapped.title())
                            result_ilce = self.ilce_original.get((chunk, mapped), original)
                            confidence = 0.9
                            return {'il': result_il, 'ilce': result_ilce, 'confidence': confidence, 'needs_gemini': False}

                for chunk_orig in [chunk_space_cleaned, chunk_nospace_cleaned]:
                    for suffix in ['TAN', 'TA', 'DAN', 'DA', 'YA', 'YE', 'E', 'EN', 'IN', 'DEN', 'N', 'NE']:
                        if chunk_orig.endswith(suffix):
                            prefix = chunk_orig[:-len(suffix)]
                            if prefix and (prefix in self.il_to_ilceler or prefix in self.ilce_to_il):
                                if prefix in self.il_to_ilceler:
                                    result_il = self.il_original.get(prefix, prefix.title())
                                    result_ilce = self._get_default_ilce(prefix, text)
                                    confidence = 0.85
                                    return {'il': result_il, 'ilce': result_ilce or '', 'confidence': confidence, 'needs_gemini': False}
                                elif prefix in self.ilce_to_il:
                                    mapped = self.ilce_to_il.get(prefix)
                                    if mapped:
                                        result_il = self.il_original.get(mapped, mapped.title())
                                        result_ilce = self.ilce_original.get((prefix, mapped), prefix)
                                        confidence = 0.85
                                        return {'il': result_il, 'ilce': result_ilce, 'confidence': confidence, 'needs_gemini': False}

        if AI_VALIDATOR_AVAILABLE and AILocationValidator:
            try:
                api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
                if not api_key:
                    try:
                        from src.utils.api_key_manager import get_default_manager
                        akm = get_default_manager()
                        akm.load_keys()
                        api_key = akm.get_active_key()
                    except Exception:
                        import logging
                        logging.getLogger(__name__).exception('Failed to load API key via APIKeyManager')

                if api_key:
                    validator = AILocationValidator(str(Path(__file__).resolve().parent.parent / 'il_ilçeler.json'), api_key)
                    search_text = location_text or f"{il or ''} {ilce or ''}".strip()
                    if search_text:
                        result = validator.validate_location(ilce or il or '', il or '')
                        if result.il and result.confidence > 0.5:
                            return {
                                'il': result.il,
                                'ilce': result.ilce,
                                'confidence': min(result.confidence, 0.8),
                                'needs_gemini': False
                            }
            except Exception:
                import logging
                logging.getLogger(__name__).exception('AI location validator call failed')
                pass

        return {'il': '', 'ilce': '', 'confidence': 0.0, 'needs_gemini': True}

    def match(self, message_body: str) -> dict:
        text = _normalize(message_body)
        tokens = [t for t in text.replace(',', ' ').split() if t]
        n = len(tokens)
        for i in range(n):
            for j in range(i + 1, min(i + 4, n + 1)):
                chunk_space = ' '.join(tokens[i:j])
                chunk_nospace = ''.join(tokens[i:j])
                chunk_asci = _asciifold_nospace(chunk_space)
                if chunk_space in self.il_to_ilceler or chunk_nospace in self.il_to_ilceler or chunk_asci in self.il_to_ilceler:
                    if chunk_space in self.il_to_ilceler:
                        key = chunk_space
                    elif chunk_nospace in self.il_to_ilceler:
                        key = chunk_nospace
                    else:
                        key = chunk_asci
                    return {'confidence': 0.9, 'matches': [{'type': 'il', 'value': self.il_original.get(key, key.title())}]}
                if chunk_space in self.ilce_to_il or chunk_nospace in self.ilce_to_il or chunk_asci in self.ilce_to_il:
                    if chunk_space in self.ilce_to_il:
                        key = chunk_space
                    elif chunk_nospace in self.ilce_to_il:
                        key = chunk_nospace
                    else:
                        key = chunk_asci
                    il_upper = self.ilce_to_il[key]
                    return {'confidence': 0.9, 'matches': [{'type': 'ilce', 'value': self.ilce_original.get((key, il_upper), chunk_space), 'il': self.il_original.get(il_upper, il_upper)}]}
        return {'confidence': 0.0, 'matches': []}

    def parse_location(self, location_text: str) -> dict:
        """Compatibility wrapper expected by parsers: returns dict with keys 'il','ilce','confidence','needs_gemini'."""
        try:
            return self.validate_and_fix(None, None, location_text)
        except Exception:
            return {'il': '', 'ilce': '', 'confidence': 0.0, 'needs_gemini': True}
            return {'confidence': 0.0, 'matches': []}

        def parse_location(self, location_text: str) -> dict:
            """Compatibility wrapper expected by parsers: returns dict with keys 'il','ilce','confidence','needs_gemini'."""
            try:
                return self.validate_and_fix(None, None, location_text)
            except Exception:
                return {'il': '', 'ilce': '', 'confidence': 0.0, 'needs_gemini': True}
