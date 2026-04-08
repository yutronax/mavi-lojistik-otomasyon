
import json
import os
import re
import logging
import unicodedata
from typing import Dict, List, Optional, Set

logger = logging.getLogger(__name__)

class VehicleTypeMatcher:
    """
    Matches vehicle, body, and load types based on rules defined in 'yuk_tipi.json'.
    """

    def __init__(self, data_path: str = None):
        if data_path is None:
            # Default to data/yuk_tipi.json relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_path = os.path.join(base_dir, 'data', 'yuk_tipi.json')
        
        self.data_path = data_path
        self.rules = []
        self._load_rules()

    def _load_rules(self):
        try:
            if not os.path.exists(self.data_path):
                logger.error(f"Vehicle type rules file not found: {self.data_path}")
                return

            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Sort rules by priority (high to low)
            # Ensure priority exists, default to 0 if not
            self.rules = sorted(data, key=lambda x: x.get('priority', 0), reverse=True)
            logger.info(f"Loaded {len(self.rules)} vehicle type rules.")
            
        except Exception as e:
            logger.error(f"Failed to load vehicle type rules: {e}")

    def _normalize(self, text: str) -> str:
        """
        Normalize text for matching:
        - Uppercase with Turkish char handling (i/ı normalization)
        - Clean newlines and tabs
        - Normalize unicode
        """
        if not text:
            return ""
        
        # Clean newlines and tabs to avoid spacing issues
        text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        
        # Unicode normalization
        text = unicodedata.normalize('NFKC', text)
        
        # Turkish-specific char replacement (Mapping complex chars to simple uppercase)
        # We map both i and ı to I to handle keyboard/typing variations
        replacements = {
            'i': 'I', 'ı': 'I', 'İ': 'I', 'I': 'I',
            'ğ': 'G', 'ü': 'U', 'ş': 'S', 'ö': 'O', 'ç': 'C',
            'Ğ': 'G', 'Ü': 'U', 'Ş': 'S', 'Ö': 'O', 'Ç': 'C'
        }
        
        # Remove common punctuation noise that might be inside words before normalizing
        # but keep spaces for tokenization later.
        text = re.sub(r'[\-\.\,\/\+\(\)\[\]]', '', text)
        
        res = ""
        for char in text:
            res += replacements.get(char, char.upper())
            
        return res.strip()
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text into keywords (split on spaces after cleaning punctuation)"""
        if not text:
            return []
            
        # 1. Replace word-joining punctuation with spaces
        # (This separates 'DAMPERLİ/TIR' into 'DAMPERLİ' and 'TIR')
        text = re.sub(r'[\,\/\+\(\)\[\]]', ' ', text)
        
        # 2. Remove purely joining characters like dot or dash 
        # (Allows '13.60' -> '1360' and 'ısuz-u' -> 'ısuzu')
        cleaned = re.sub(r'[\.\-]', '', text)
        
        # 2. Split on any whitespace
        tokens = cleaned.split()
        return [self._normalize(t) for t in tokens if t.strip()]

    @staticmethod
    def _levenshtein_distance(s1: str, s2: str) -> int:
        """Calculates the Levenshtein distance between two strings."""
        if len(s1) < len(s2):
            return VehicleTypeMatcher._levenshtein_distance(s2, s1)

        if len(s2) == 0:
            return len(s1)

        previous_row = range(len(s2) + 1)
        for i, c1 in enumerate(s1):
            current_row = [i + 1]
            for j, c2 in enumerate(s2):
                insertions = previous_row[j + 1] + 1
                deletions = current_row[j] + 1
                substitutions = previous_row[j] + (c1 != c2)
                current_row.append(min(insertions, deletions, substitutions))
            previous_row = current_row
        
        return previous_row[-1]

    def _match_pattern_in_tokens(self, pattern_tokens: List[str], text_tokens: List[str]) -> Dict:
        """
        Checks if pattern_tokens exist in text_tokens (Exact or Fuzzy).
        Returns {'match': bool, 'score': float, 'indices': List[int]}
        """
        if not pattern_tokens or not text_tokens:
            return {'match': False, 'score': 0.0, 'indices': []}
            
        pat_len = len(pattern_tokens)
        text_len = len(text_tokens)
        
        # Case 1: Exact Subsequence Check (Preferred)
        for i in range(text_len - pat_len + 1):
            window = text_tokens[i : i + pat_len]
            if window == pattern_tokens:
                return {'match': True, 'score': 1.0, 'indices': list(range(i, i + pat_len))}
        
        # Case 2: Fuzzy Match
        fuzzy_threshold = 0.80 # Lowered from 0.90 to capture more typos like 'isizu'
        best_score = 0.0
        best_indices = []
        
        if pat_len > text_len:
            return {'match': False, 'score': 0.0, 'indices': []}
            
        for i in range(text_len - pat_len + 1):
            window = text_tokens[i : i + pat_len]
            
            total_dist = 0
            total_len = 0
            match_failed = False
            
            for p_t, w_t in zip(pattern_tokens, window):
                # 1. Strict Numeric Check: Numbers MUST match exactly
                p_is_num = p_t.isdigit()
                w_is_num = w_t.isdigit()
                
                if p_is_num or w_is_num:
                    if p_t != w_t:
                        # logger.info(f"Numeric Mismatch: {p_t} != {w_t}")
                        match_failed = True
                        break
                    total_len += len(p_t)
                    continue

                # 2. Substring/Suffix Check (Only for NON-NUMERIC tokens)
                if p_t in w_t and len(w_t) - len(p_t) <= 3:
                      total_len += len(w_t)
                      continue

                # 3. Major length mismatch check (Non-numeric)
                if abs(len(p_t) - len(w_t)) > 2:
                    match_failed = True
                    break
                    
                total_dist += self._levenshtein_distance(p_t, w_t)
                total_len += max(len(p_t), len(w_t))
                
            if match_failed:
                continue
                
            similarity = 1 - (total_dist / total_len) if total_len > 0 else 0
            
            if similarity >= fuzzy_threshold and similarity > best_score:
                best_score = similarity
                best_indices = list(range(i, i + pat_len))

        if best_score >= fuzzy_threshold:
            return {'match': True, 'score': best_score, 'indices': best_indices}
            
        return {'match': False, 'score': 0.0, 'indices': []}

    def _smart_merge(self, sets: List[Set[str]]) -> Set[str]:
        """
        Merges sets using subset optimization (generic vs specific) and then combining the unique traits.
        Instead of blindly taking intersections and dropping diverse properties (e.g. FRİGO + KAPALI),
        this extracts pure independent rules and unions them.
        """
        if not sets:
            return set()
            
        # First, filter out noisy/generic supersets
        optimized_sets = self._optimize_subsets(sets)
        
        # Now union all the remaining independent traits
        result = set()
        for s in optimized_sets:
            result.update(s)
            
        return result

    def _optimize_subsets(self, set_list: List[Set[str]]) -> List[Set[str]]:
        """
        Applies subset optimization logic to a list of sets.
        If Set A is a proper subset of Set B, keep A and discard B.
        Logic: Specific constraint overrides generic list.
        Example: {1360} overrides {1360, 40 AYAK}.
        """
        if not set_list:
            return []
            
        # Remove duplicates
        unique_sets = []
        for s in set_list:
            if s not in unique_sets:
                unique_sets.append(s)
        
        final_sets = []
        for s in unique_sets:
            is_superset = False
            for other in unique_sets:
                if s == other:
                    continue
                if other.issubset(s) and other != s:
                    # 'other' is smaller/more specific. 's' is generic/superset.
                    # e.g. other={KAPALI} (Size 1), s={AÇIK, KAPALI} (Size 2).
                    # KAPALI is in AÇIK+KAPALI.
                    # So we discard 's'.
                    is_superset = True
                    break
            
            if not is_superset:
                final_sets.append(s)
                
        return final_sets

    def find_all_matches(self, message: str) -> Dict:
        """
        Finds ALL matches in the message by iteratively consuming matched tokens.
        Returns a merged dictionary of unique values with subset/priority logic.
        """
        if not message:
            return {}

        norm_message = self._normalize(message)
        text_tokens = self._tokenize(message)
        working_tokens = text_tokens[:] 
        
        matches_found = False
        
        # Collect raw outputs to handle subset logic
        found_vehicles = [] # List of sets
        found_bodies = []   # List of sets
        found_loads = set()
        
        # 0. TEKER Logic: Standalone "teker" -> 10 TEKER, "4 teker" -> 4 TEKER, etc.
        # We process this early because it's a structural rule with numeric variation.
        for i, token in enumerate(working_tokens):
            if not token: continue
            
            # Case 1: "4TEKER" or similar (joined)
            match = re.search(r'^(\d+)TEKER$', token)
            if match:
                num = match.group(1)
                found_vehicles.append({f"{num} TEKER"})
                working_tokens[i] = None
                matches_found = True
                # Look back for more numbers if multiple mentioned (e.g., "4 6 8TEKER")
                j = i - 1
                while j >= 0 and working_tokens[j] and working_tokens[j].isdigit():
                    found_vehicles.append({f"{working_tokens[j]} TEKER"})
                    working_tokens[j] = None
                    j -= 1
                continue
            
            # Case 2: "TEKER" (standalone or with separate numbers)
            if token == "TEKER":
                j = i - 1
                found_any_num = False
                # Scan backwards for all numbers separated by spaces/punctuation
                while j >= 0 and working_tokens[j] and working_tokens[j].isdigit():
                    num = working_tokens[j]
                    found_vehicles.append({f"{num} TEKER"})
                    working_tokens[j] = None
                    found_any_num = True
                    j -= 1
                
                if not found_any_num:
                    # Default to 10 TEKER if no number found
                    found_vehicles.append({"10 TEKER"})
                
                working_tokens[i] = None
                matches_found = True

        # Iterate rules by priority
        for rule in self.rules:
            pattern = rule.get('orjinal mesajdaki')
            if not pattern:
                continue
                
            pattern_tokens = self._tokenize(pattern)
            if not pattern_tokens:
                continue

            # Iterate while valid tokens exist
            while True:
                valid_indices_map = [i for i, t in enumerate(working_tokens) if t is not None]
                valid_tokens = [working_tokens[i] for i in valid_indices_map]
                
                if not valid_tokens:
                    break
                    
                match_data = self._match_pattern_in_tokens(pattern_tokens, valid_tokens)
                
                if match_data['match']:
                    out = rule.get('kesin_cikti', {})
                    matches_found = True
                    
                    # 1. Collect Data
                    y_tipi = out.get("YÜKÜN TİPİ")
                    if y_tipi:
                        if isinstance(y_tipi, list):
                            for y in y_tipi: found_loads.add(y)
                        else:
                            found_loads.add(y_tipi)
                        
                    k_str_val = out.get("KASA TİPİ")
                    if k_str_val: 
                        if isinstance(k_str_val, list):
                             found_bodies.append(set(k_str_val))
                        else:
                             k_set = set([x.strip() for x in k_str_val.split('+')])
                             found_bodies.append(k_set)
                        
                    v_str_val = out.get("ARAÇ TİPİ")
                    if v_str_val:
                        if isinstance(v_str_val, list):
                             found_vehicles.append(set(v_str_val))
                        else:
                             v_set = set([x.strip() for x in v_str_val.split('+')])
                             found_vehicles.append(v_set)

                    # 2. Mark consumed
                    matched_valid_indices = match_data['indices']
                    for v_idx in matched_valid_indices:
                        real_idx = valid_indices_map[v_idx]
                        working_tokens[real_idx] = None 
                    
                else:
                    break # Next rule

        # --- Business Rules (Run even if no patterns matched) ---
        # 1. METRE / PAKET / TON = PARÇA
        parca_keywords = {"METRE", "MT", "METRELIK", "PAKET", "PAK", "KOLI", "PALETLI", "PARCA", "PARSIYEL", "PARSİYEL"}
        if any(kw in norm_message for kw in parca_keywords):
            found_loads.add("PARÇA")
        
        # 2. Numeric + M = METRE = PARÇA
        if re.search(r'\b\d+(?:\.\d+)?\s*M\b', norm_message):
            found_loads.add("PARÇA")
        
        # 3. PALET / TON Count Check
        numeric_matches = re.findall(r'(\d+)\s*(?:PALET|PLT|PALETLİ|PALETLI|TON|TONLUK|T)', norm_message)
        for count_str in numeric_matches:
            try:
                count = int(count_str)
                if "PALET" in norm_message or "PLT" in norm_message:
                    if count >= 7:
                        found_loads.add("PARÇA")
                else:
                    if count < 10:
                        found_loads.add("PARÇA")
            except ValueError:
                pass

        # 4. Tarım/Dökme/Sebze Kuralı (Buğday, Soğan, Meyve, Sebze, Yem vb.)
        # Kullanıcının talebi: Bu yüklerde direkt 860 aransın, diğer araçlar varsa birleşsin.
        tarim_keywords = {
            # Tahıl, Bakliyat ve Yem Grubu
            "BUGDAY", "SOGAN", "MEYVE", "SEBZE", "YEM", "MISIR", 
            "PATATES", "DOMATES", "ARPA", "YULAF", "SAMAN", "KUSPE", "GUBRE", "KEPEK",
            "NOHUT", "MERCIMEK", "FASULYE", "PIRINC", "BAKLIYAT", "SILAJ", "YONCA", "FIY", "MANGAL KOMURU",
            # Endüstriyel Tarım ve Diğer Ürünler
            "PANCAR", "SEKER PANCARI", "AYCICEGI", "CEKIRDEK", "PAMUK", "SOYA",
            # Dökme İnşaat, Maden ve Orman Ürünleri (Bunlar da genelde 860 damperli kullanır)
            "KUM", "CAKIL", "MICIR", "HAFRIYAT", "MOLOZ", "TOPRAK", "MADEN", "CEVHER", 
            "HURDA", "ODUN", "TALAS"
        }
        if any(kw in text_tokens for kw in tarim_keywords):
            found_vehicles.append({"860"})
            # Tarım ürünleri "KOMPLE" den ziyade "DÖKME" (veya parçalı değilse genel tonaj) olabilir
            # Ancak kullanıcı özel olarak yük tipinden bahsetmemiş, sadece aracı 860 yapsın istemiş.
            found_loads.add("DÖKME")


        if matches_found or found_loads or found_vehicles or found_bodies:
            final_output = {}
            
            # --- Merge sets using Smart Intersection Logic ---
            merged_vehicles = self._smart_merge(found_vehicles)
            merged_bodies = self._smart_merge(found_bodies)
            
            # --- Load Type Prioritization ---
            non_paletli_specifics = {"PARÇA", "DÖKME", "KOLİ", "ÇUVALLI"}
            has_non_paletli = not found_loads.isdisjoint(non_paletli_specifics)
            
            if has_non_paletli and "KOMPLE" in found_loads:
                found_loads.remove("KOMPLE")
            
            if "PALETLİ" in found_loads and "KOMPLE" in found_loads:
                if not merged_vehicles.isdisjoint({"TIR", "1360"}):
                    found_loads.remove("KOMPLE")

            # --- Lowbed Exclusivity ---
            if "LOWBED" in merged_bodies:
                merged_bodies = {"LOWBED"}

            # --- Strict Frigo Logic ---
            if "FRİGO" in merged_bodies:
                # Removed "DAMPERLİ" from conflicting types so it doesn't drop explicit 860 requirements
                conflicting_types = {"AÇIK", "SÇIK"}
                merged_bodies = {b for b in merged_bodies if b not in conflicting_types}
                
                frigo_keywords = {"FRİGO", "TERMOKİN", "SOĞUTUCU", "FRIGO", "TERMOKIN", "SOGUTUCU"}
                if not any(kw in norm_message for kw in frigo_keywords):
                    merged_bodies.discard("FRİGO")
                
            # Neutral Element Logic for TIR (1360) ---
            # If multiple vehicle types are found (e.g. 860 and 1360),
            # only discard 1360 if it wasn't explicitly mentioned in the text (e.g. as a generic fallback).
            if len(merged_vehicles) > 1 and "1360" in merged_vehicles:
                explicit_1360_kws = {"1360", "13 60", "13 6", "TIR", "TİR"} 
                if not any(kw in norm_message for kw in explicit_1360_kws):
                    merged_vehicles.discard("1360")

            if found_loads: final_output["YÜKÜN TİPİ"] = " + ".join(sorted(list(found_loads)))
            if merged_vehicles: final_output["ARAÇ TİPİ"] = " + ".join(sorted(list(merged_vehicles)))
            if merged_bodies: final_output["KASA TİPİ"] = " + ".join(sorted(list(merged_bodies)))
            
            return final_output
            
        return None

    def get_relevant_rules(self, message: str, limit: int = 20) -> List[Dict]:
        """
        Finds rules in yuk_tipi.json that are relevant to the given message.
        Returns a list of rule objects (orjinal, priority, kesin_cikti).
        Used for dynamic context injection in LLM prompts.
        """
        if not message:
            return []

        norm_message = self._normalize(message)
        text_tokens = self._tokenize(message)
        
        relevant_rules = []
        seen_patterns = set()

        # 1. Higher priority to rules that have an exact match in tokens
        for rule in self.rules:
            pattern = rule.get('orjinal mesajdaki')
            if not pattern or pattern in seen_patterns:
                continue
                
            pattern_tokens = self._tokenize(pattern)
            if not pattern_tokens:
                continue

            match_data = self._match_pattern_in_tokens(pattern_tokens, text_tokens)
            
            if match_data['match']:
                # Simplify rule for prompt to save space
                simplified_rule = {
                    "pattern": pattern,
                    "output": rule.get('kesin_cikti', {}),
                    "priority": rule.get('priority', 0),
                    "score": match_data.get('score', 1.0)
                }
                relevant_rules.append(simplified_rule)
                seen_patterns.add(pattern)
                
                if len(relevant_rules) >= limit:
                    break

        # Filter out rules with empty kesin_cikti if they are just noise
        relevant_rules = [r for r in relevant_rules if r['output']]
        
        # Sort by priority and then by score
        relevant_rules.sort(key=lambda x: (x['priority'], x['score']), reverse=True)
        
        return relevant_rules[:limit]

    def find_match(self, message: str, per_route: bool = False) -> Optional[Dict]:
        return self.find_all_matches(message)

    def apply_to_shipment(self, shipment: Dict, original_message: str) -> Dict:
        text_to_scan = original_message or shipment.get('orijinal_mesaj') or shipment.get('aciklama') or ""
        match = self.find_all_matches(text_to_scan)
        if match:
            if match.get("YÜKÜN TİPİ"):
                shipment['yuk_tipi'] = [match["YÜKÜN TİPİ"]]
            if match.get("ARAÇ TİPİ"):
                val = match["ARAÇ TİPİ"]
                shipment['arac_tipi'] = [v.strip() for v in val.split('+')]
            if match.get("KASA TİPİ"):
                val = match["KASA TİPİ"]
                shipment['kasa_tipi'] = [v.strip() for v in val.split('+')]
        return shipment
