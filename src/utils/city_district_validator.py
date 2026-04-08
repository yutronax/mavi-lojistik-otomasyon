import json
import os
import re
import logging
import unicodedata
from typing import Dict, List, Tuple, Optional

logger = logging.getLogger(__name__)

class CityDistrictValidator:
    """
    Validates city (il) and district (ilçe) pairs using a JSON data file.
    Ensures that for a given city, the district is actually valid.
    """

    def __init__(self, data_path: str = None):
        if data_path is None:
            # Default to data/il_ilçe_mahalle.json relative to project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            data_path = os.path.join(base_dir, 'data', 'il_ilçe_mahalle.json')
        
        self.data_path = data_path
        self.city_map = {}  # Normalized City -> Set of normalized Districts
        self.district_reverse_map = {} # Normalized District -> List of Cities containing it
        
        self._load_data()

    def _normalize(self, text: str) -> str:
        """
        Uppercase and handles Turkish characters correctly with Unicode normalization.
        Ensures decomposed characters (like I + dot) are merged into proper Turkish İ.
        """
        if not text:
            return ""
        
        # 1. Preliminary NFC normalization to merge existing decomposed marks
        text = unicodedata.normalize('NFC', text)
        
        # 2. Manual uppercase for Turkish (i -> İ, ı -> I)
        # Avoids logic bugs where .lower() decomposes 'İ' back to 'i' + 'dot'
        repls = {'i': 'İ', 'ı': 'I', 'ş': 'Ş', 'ğ': 'Ğ', 'ü': 'Ü', 'ö': 'Ö', 'ç': 'Ç'}
        upper_text = ""
        for char in text:
            if char in repls:
                upper_text += repls[char]
            elif char == 'İ' or char == 'I':
                upper_text += char # Preserve already uppercase
            else:
                upper_text += char.upper()
        
        # 3. Final NFC normalization to ensure any newly formed compositions are correct
        return unicodedata.normalize('NFC', upper_text).strip()

    def _load_data(self):
        try:
            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.default_districts = {}
            
            for entry in data:
                city = self._normalize(entry.get('il', ''))
                if not city:
                    continue
                
                districts = []
                # Support for new 'ilceler' hierarchical structure
                if 'ilceler' in entry:
                    for d_obj in entry.get('ilceler', []):
                        d_name = self._normalize(d_obj.get('ilce', ''))
                        if d_name:
                            districts.append(d_name)
                # Fallback to old 'ilçe' flat structure
                elif 'ilçe' in entry:
                    districts = [self._normalize(d) for d in entry.get('ilçe', [])]
                
                # Default district handling (optional in new format)
                default_dist = self._normalize(entry.get('varsayılan_ilçe', ''))
                if not default_dist and districts:
                    # Heuristic: if no default, use 'MERKEZ' or first one
                    default_dist = 'MERKEZ' if 'MERKEZ' in districts else districts[0]
                
                if city:
                    self.city_map[city] = set(districts)
                    if default_dist:
                        self.default_districts[city] = default_dist
                        
                    for d in districts:
                        if d not in self.district_reverse_map:
                            self.district_reverse_map[d] = []
                        self.district_reverse_map[d].append(city)
            
            # Explicit Default Overrides / Additions
            # Handling "İSTANBUL ANADOLU" and "İSTANBUL AVRUPA" as pseudo-defaults
            # We map specific keywords if they appear as CITY input to normalized specific districts
            
            logger.info(f"Loaded {len(self.city_map)} cities for validation.")
            
        except Exception as e:
            logger.error(f"Failed to load city data from {self.data_path}: {e}")
            # Do not crash; validation will just be pass-through or minimal

    def validate(self, city: str, district: str) -> Tuple[str, str]:
        """
        Validates and possibly corrects the city-district pair using strict and fuzzy logic.
        """
        norm_city = self._normalize(city)
        norm_dist = self._normalize(district)
        
        # --- SPECIAL HANDLING FOR ISTANBUL SIDES ---
        # User defined defaults: İSTANBUL ANADOLU -> MALTEPE, İSTANBUL AVRUPA -> AVCILAR
        # We strip the side info from city name to allow validation, but override default if district is missing.
        forced_default = None
        if "İSTANBUL" in norm_city:
            if "ANADOLU" in norm_city:
                norm_city = "İSTANBUL"
                forced_default = "MALTEPE"
            elif "AVRUPA" in norm_city:
                norm_city = "İSTANBUL"
                forced_default = "AVCILAR"
        
        # Handle when "ANADOLU" or "AVRUPA" appears as district name for Istanbul
        if norm_city == "İSTANBUL":
            if norm_dist == "ANADOLU":
                norm_dist = "MALTEPE"
                logger.info(f"Istanbul district 'ANADOLU' -> 'MALTEPE'")
            elif norm_dist == "AVRUPA":
                norm_dist = "AVCILAR"
                logger.info(f"Istanbul district 'AVRUPA' -> 'AVCILAR'")

        # If basics missing, just return normalized
        if not norm_city:
            return norm_city, norm_dist

        # If we have no data, pass through
        if not self.city_map:
            return norm_city, norm_dist

        # If district is empty or MERKEZ, matches ANY city (basically)
        if not norm_dist or norm_dist == 'MERKEZ':
            # Check if city itself is valid or fuzzy matchable
            effective_city = norm_city
            if norm_city not in self.city_map:
                fuzzy = self._fuzzy_match_city(norm_city)
                if fuzzy:
                    logger.info(f"Fuzzy City Match: '{norm_city}' -> '{fuzzy}'")
                    effective_city = fuzzy
            
            # --- APPLY DEFAULT DISTRICT ---
            # If we resolved to a valid city, check if we should apply a default
            if effective_city in self.city_map:
                # Use forced (Istanbul side) default if applicable
                if forced_default and effective_city == "İSTANBUL":
                    logger.info(f"Applying Side-Specific Default: '{effective_city}' -> '{forced_default}'")
                    return effective_city, forced_default
                
                # Use standard default from JSON data
                default = self.default_districts.get(effective_city)
                if default:
                     # Strict replacement: If input was empty OR 'MERKEZ', upgrade to specific default
                     # User rule: "eğer merkez yazılmışsa direkt bu yapılmalı"
                     logger.info(f"Applying Default District (Strict): '{effective_city}' -> '{default}' (was '{norm_dist}')")
                     return effective_city, default
            
            return effective_city, 'MERKEZ'

        # Check if city exists exact
        valid_districts = self.city_map.get(norm_city)
        
        # 1. City Exact Match, District Exact Match
        if valid_districts and norm_dist in valid_districts:
            return norm_city, norm_dist
            
        # 2. City Exact Match, District Fuzzy or Mismatch
        if valid_districts:
            # Try fuzzy match district within this city
            fuzzy_d = self._fuzzy_match_district(norm_dist, valid_districts)
            if fuzzy_d:
                logger.info(f"District Fuzzy Correct: '{norm_dist}' -> '{fuzzy_d}' (in {norm_city})")
                return norm_city, fuzzy_d

        # 3. City Not Found (or Mismatch), Check Reverse Lookup for District
        # Case: "TIRE" -> "İZMİR" (City was empty or wrong, District was correct/fuzzy)
        
        # First try assuming 'district' input is actually a valid district somewhere
        # Check exact district lookup
        if norm_dist in self.district_reverse_map:
             cities = self.district_reverse_map[norm_dist]
             if len(cities) == 1:
                 # Unique match (e.g. Pendik -> Istanbul)
                 # Override city if original was wrong/empty
                 if norm_city not in cities:
                     logger.info(f"City Correction by Unique District: '{norm_city}' -> '{cities[0]}' (via '{norm_dist}')")
                     return cities[0], norm_dist
        
        # Check fuzzy district lookup in entire dataset (expensive but worth for TIRE -> TİRE)
        # However, entire district list is huge. Let's optimize:
        # If 'norm_dist' is very close to a known district like 'TİRE' (normalized), map it.
        # But we don't have a flat list of all normalized districts easily accessible in generic fuzzy match.
        # We constructed 'district_reverse_map' keys as normalized districts.
        
        fuzzy_global_dist = self._fuzzy_match_district_global(norm_dist)
        if fuzzy_global_dist:
             # If we found a global fuzzy match (e.g. TIRE -> TİRE)
             cities = self.district_reverse_map[fuzzy_global_dist]
             if len(cities) == 1:
                 logger.info(f"Global District Fuzzy & City Correction: '{norm_city}' + '{norm_dist}' -> '{cities[0]}' + '{fuzzy_global_dist}'")
                 return cities[0], fuzzy_global_dist
             elif norm_city in cities:
                 # It was valid city, just typo in district
                 return norm_city, fuzzy_global_dist
        
        # 4. City Fuzzy Match (if city was the issue and district didn't help)
        fuzzy_city = self._fuzzy_match_city(norm_city)
        if fuzzy_city:
            # Check district against fuzzy city
            valid_dists_fuzzy = self.city_map.get(fuzzy_city)
            if norm_dist in valid_dists_fuzzy:
                return fuzzy_city, norm_dist
            # Fuzzy check district in fuzzy city
            fuzzy_d_in_fuzzy_city = self._fuzzy_match_district(norm_dist, valid_dists_fuzzy)
            if fuzzy_d_in_fuzzy_city:
                 return fuzzy_city, fuzzy_d_in_fuzzy_city
            
            # Use fuzzy city, reset district if unmatched
            logger.info(f"Fuzzy City Match (District Reset): '{norm_city}' -> '{fuzzy_city}'")
            return fuzzy_city, 'MERKEZ'

        # 5. Last Resort: Ambiguous or Unknown
        # If district matches multiple cities (e.g. MERKEZ, YENIMAHALLE), and city is invalid...
        # We can't guess. 
        
        if norm_city in self.default_districts:
             default_d = self.default_districts[norm_city]
             logger.warning(f"Validation Failed: '{norm_city}' - '{norm_dist}'. Resetting to default '{default_d}'.")
             return norm_city, default_d
        
        logger.warning(f"Validation Failed: '{norm_city}' - '{norm_dist}'. Resetting district to MERKEZ.")
        return norm_city, 'MERKEZ'

    def _fuzzy_match_city(self, candidate: str) -> Optional[str]:
        """Find closest city name."""
        import difflib
        matches = difflib.get_close_matches(candidate, self.city_map.keys(), n=1, cutoff=0.7)
        return matches[0] if matches else None

    def _fuzzy_match_district(self, candidate: str, possibilities: set) -> Optional[str]:
        """Find closest district in a given set."""
        import difflib
        matches = difflib.get_close_matches(candidate, list(possibilities), n=1, cutoff=0.7)
        return matches[0] if matches else None

    def _fuzzy_match_district_global(self, candidate: str) -> Optional[str]:
        """Find closest district in ALL districts (keys of reverse map)."""
        import difflib
        # Optimization: only check if length is reasonable
        matches = difflib.get_close_matches(candidate, self.district_reverse_map.keys(), n=1, cutoff=0.7) # Relaxed cutoff for short words
        return matches[0] if matches else None
