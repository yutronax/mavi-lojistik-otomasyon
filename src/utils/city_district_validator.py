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
        # Load secondary defaults file if exists in the same directory
        self.defaults_path = os.path.join(os.path.dirname(data_path), 'il_ilçeler.json')
        
        self.city_map = {}  # Normalized City -> Set of normalized Districts
        self.district_reverse_map = {} # Normalized District -> List of Cities containing it
        self.neighborhood_map = {} # Normalized Neighborhood -> List of (City, District)
        self.default_districts = {}
        
        # District Alias Map (Kısa isimler -> Resmi isimler)
        self.district_aliases = {
            "KEMALPAŞA": "MUSTAFAKEMALPAŞA",
            "M.KEMALPAŞA": "MUSTAFAKEMALPAŞA",
            "MUSTAFA KEMAL PAŞA": "MUSTAFAKEMALPAŞA"
        }
        
        # City Alias Map (Yaygın kısaltmalar -> Resmi isimler)
        self.city_aliases = {
            "MARAŞ": "KAHRAMANMARAŞ",
            "ANTEP": "GAZİANTEP",
            "URFA": "ŞANLIURFA",
            "YAMAN": "ADIYAMAN",
            "ELAZIĞ": "ELAZIĞ", # Fix potential İ/I confusion
            "AFYON": "AFYONKARAHİSAR",
            "İÇEL": "MERSİN"
        }
        
        # Neighborhood manually injected (Stratejik eksik bölgeler)
        self.manual_neighborhoods = {
            "SİTELER": [("ANKARA", "ALTINDAĞ")],
            "OVACIK": [("ANKARA", "KEÇİÖREN")],
            "VEZİRHAN": [("BİLECİK", "MERKEZ")],
            "KEMALPAŞA": [("BURSA", "MUSTAFAKEMALPAŞA")],
            "HADIMKÖY": [("İSTANBUL", "ARNAVUTKÖY")],
            "TOPKAPI": [("İSTANBUL", "FATİH")]
        }
        
        self._load_data()

    def _normalize(self, text: str) -> str:
        """
        Turkish normalization: ensures i -> İ and ı -> I.
        Does not use upper() directly on the whole string to avoid ASCII I issues.
        """
        if not text:
            return ""
        
        # Consistent Turkish uppercase mapping
        map_low_to_up = {
            'i': 'İ', 'ı': 'I', 'ç': 'Ç', 'ğ': 'Ğ', 'ö': 'Ö', 'ş': 'Ş', 'ü': 'Ü',
            'a': 'A', 'b': 'B', 'c': 'C', 'd': 'D', 'e': 'E', 'f': 'F', 'g': 'G',
            'h': 'H', 'j': 'J', 'k': 'K', 'l': 'L', 'm': 'M', 'n': 'N', 'o': 'O',
            'p': 'P', 'r': 'R', 's': 'S', 't': 'T', 'u': 'U', 'v': 'V', 'y': 'Y',
            'z': 'Z', 'x': 'X', 'q': 'Q', 'w': 'W'
        }
        
        # 1. Normalize Unicode first
        text = unicodedata.normalize('NFC', text)
        
        # 2. Manual Uppercase
        res = ""
        for char in text:
            res += map_low_to_up.get(char, char.upper())
            
        # 3. Clean combining marks (already mostly handled by NFC + map, but for safety)
        res = unicodedata.normalize('NFC', res)
        # Remove redundant dots above I/İ
        res = res.replace('I\u0307', 'İ').replace('İ\u0307', 'İ')
        
        return res.strip()

    def _load_data(self):
        """
        Loads hierarchical data from il_ilçe_mahalle.json
        Structure: [ {"il": "CITY", "ilceler": [{"ilce": "DIST", "mahalleler": [...]}]}, ... ]
        """
        try:
            if not os.path.exists(self.data_path):
                logger.error(f"Data file not found: {self.data_path}")
                return

            with open(self.data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Clear current maps
            self.city_map = {}
            self.neighborhood_map = {}
            self.district_reverse_map = {}
            self.default_districts = {}

            for entry in data:
                city = self._normalize(entry.get('il', ''))
                if not city: continue
                
                if city not in self.city_map:
                    self.city_map[city] = set()
                
                ilceler = entry.get('ilceler', [])
                # Some files might use 'ilçe' or other keys, but hierarchical uses ilceler
                if not ilceler and 'ilçe' in entry:
                    # Handle flat list if present
                    ilceler = [{"ilce": d, "mahalleler": []} for d in entry['ilçe']]

                for d_obj in ilceler:
                    dist = self._normalize(d_obj.get('ilce', ''))
                    if not dist: continue
                    
                    self.city_map[city].add(dist)
                    
                    # Reverse map (District -> [Cities])
                    if dist not in self.district_reverse_map:
                        self.district_reverse_map[dist] = []
                    self.district_reverse_map[dist].append(city)
                    
                    # Neighborhoods (Mahalle -> [(City, District)])
                    mahs = d_obj.get('mahalleler', [])
                    for m in mahs:
                        m_norm = self._normalize(m)
                        if m_norm:
                            if m_norm not in self.neighborhood_map:
                                self.neighborhood_map[m_norm] = []
                            self.neighborhood_map[m_norm].append((city, dist))
                    
                    # Also treat district as neighborhood for lookup
                    if dist not in self.neighborhood_map:
                        self.neighborhood_map[dist] = []
                    if (city, dist) not in self.neighborhood_map[dist]:
                        self.neighborhood_map[dist].append((city, dist))

            # Load curated defaults if exists
            if os.path.exists(self.defaults_path):
                try:
                    with open(self.defaults_path, 'r', encoding='utf-8') as f:
                        defaults = json.load(f)
                    for item in defaults:
                        c = self._normalize(item.get('il', ''))
                        d = self._normalize(item.get('varsayılan_ilçe', ''))
                        if c and d:
                            self.default_districts[c] = d
                except: pass

            # Set automatic defaults for cities without one
            for city in self.city_map:
                if city not in self.default_districts:
                    dists = list(self.city_map[city])
                    if 'MERKEZ' in dists:
                         self.default_districts[city] = 'MERKEZ'
                    elif dists:
                         self.default_districts[city] = sorted(dists)[0]

            logger.info(f"Loaded {len(self.city_map)} cities and {len(self.neighborhood_map)} unique neighborhood strings.")
            print(f"DEBUG: Cities={len(self.city_map)}, Neighborhoods={len(self.neighborhood_map)}")

        except Exception as e:
            logger.error(f"Error loading city data: {e}")

    def validate(self, city: str, district: str) -> Tuple[str, str]:
        """
        Validates and corrects the city-district pair with a STRICT HIERARCHY.
        
        1. PRECISE CITY MATCH: If city is valid, only search within that city.
        2. UNIQUE DISTRICT MATCH: If city is ambiguous, check if district is unique in Turkey.
        3. FUZZY CITY/DISTRICT: Fix typos.
        4. NEIGHBORHOOD LOOKUP: Global search (only if previous steps fail).
        """
        norm_city = self._normalize(city)
        norm_dist = self._normalize(district)
        
        # Apply Alias mapping (e.g., KEMALPAŞA -> MUSTAFAKEMALPAŞA)
        if norm_dist in self.district_aliases:
            norm_dist = self.district_aliases[norm_dist]
        
        # Handle Istanbul sides
        forced_default = None
        if "İSTANBUL" in norm_city:
            if "ANADOLU" in norm_city:
                norm_city, forced_default = "İSTANBUL", "MALTEPE"
            elif "AVRUPA" in norm_city:
                norm_city, forced_default = "İSTANBUL", "AVCILAR"
        
        if norm_city == "İSTANBUL":
            if norm_dist == "ANADOLU": norm_dist = "MALTEPE"
            elif norm_dist == "AVRUPA": norm_dist = "AVCILAR"

        if not norm_city and not norm_dist:
            return "", ""

        # --- STEP 1: PRECISE CITY MATCH (The "Hard" Filter) ---
        if norm_city in self.city_map:
            valid_dists = self.city_map[norm_city]
            
            # A. Check if input is directly a district in this city
            if norm_dist in valid_dists:
                return norm_city, norm_dist
            
            # B. Check if input is a neighborhood/village in this city
            if norm_dist in self.neighborhood_map:
                for c, d in self.neighborhood_map[norm_dist]:
                    if c == norm_city:
                        return c, d
            
            # C. Fuzzy match district ONLY within this city
            if norm_dist and len(norm_dist) > 2:
                fuzzy_d = self._fuzzy_match_district(norm_dist, valid_dists)
                if fuzzy_d: return norm_city, fuzzy_d
            
            # D. Fallback to default district for this city
            return norm_city, forced_default or self.default_districts.get(norm_city, 'MERKEZ')

        # --- STEP 2: UNIQUE DISTRICT MATCH (Reverse Lookup) ---
        if norm_dist in self.district_reverse_map:
            cities = self.district_reverse_map[norm_dist]
            if len(cities) == 1:
                return cities[0], norm_dist
            # If city was provided but didn't match exactly, try to find it in the options
            if norm_city:
                for c in cities:
                    if norm_city in c or c in norm_city: return c, norm_dist

        # --- STEP 3: FUZZY CITY ---
        fuzzy_c = self._fuzzy_match_city(norm_city)
        if fuzzy_c:
            valid_dists = self.city_map[fuzzy_c]
            if norm_dist in valid_dists:
                return fuzzy_c, norm_dist
            # Check neighborhood in this fuzzy city
            if norm_dist in self.neighborhood_map:
                for c, d in self.neighborhood_map[norm_dist]:
                    if c == fuzzy_c: return c, d
            
            fuzzy_d = self._fuzzy_match_district(norm_dist, valid_dists)
            return fuzzy_c, fuzzy_d or self.default_districts.get(fuzzy_c, 'MERKEZ')

        # --- STEP 4: GLOBAL NEIGHBORHOOD LOOKUP (The Last Resort) ---
        # Only search 73,000 neighborhoods if we have no clear city or district match
        if norm_dist in self.neighborhood_map:
            res = self.neighborhood_map[norm_dist]
            # If city matches partially
            if norm_city:
                for c, d in res:
                    if norm_city in c: return c, d
            return res[0]

        # --- STEP 5: GLOBAL FUZZY DISTRICT ---
        fuzzy_global_d = self._fuzzy_match_district_global(norm_dist)
        if fuzzy_global_d:
            cities = self.district_reverse_map[fuzzy_global_d]
            return cities[0], fuzzy_global_d

        return norm_city or "BİLİNMEYEN", norm_dist or "MERKEZ"

    def get_loc_context(self, message: str) -> str:
        """
        Scans message for keywords and returns relevant official location registry.
        Supports Aliases (Maraş, Urfa) and Fuzzy matches for typos.
        """
        if not message:
            return ""
            
        norm_msg = self._normalize(message)
        tokens = re.findall(r'\b\w+\b', norm_msg)
        search_space = tokens + [" ".join(tokens[i:i+2]) for i in range(len(tokens)-1)]
        
        found_cities = set()
        found_districts = set() # (City, Dist)
        neighborhood_hints = []
        
        valid_cities_list = list(self.city_map.keys())
        valid_districts_list = list(self.district_reverse_map.keys())

        import difflib

        for term in search_space:
            target_city = None
            target_dist = None
            
            # A. Check City (Exact or Alias or Fuzzy)
            if term in self.city_map:
                target_city = term
            elif term in self.city_aliases:
                target_city = self.city_aliases[term]
            else:
                fuzzy_city_matches = difflib.get_close_matches(term, valid_cities_list, n=1, cutoff=0.85)
                if fuzzy_city_matches: target_city = fuzzy_city_matches[0]

            if target_city:
                found_cities.add(target_city)

            # B. Check District (Exact or Alias or Fuzzy)
            resolved_dist = term
            if term in self.district_aliases:
                resolved_dist = self.district_aliases[term]
            
            if resolved_dist in self.district_reverse_map:
                target_dist = resolved_dist
            else:
                fuzzy_dist_matches = difflib.get_close_matches(resolved_dist, valid_districts_list, n=1, cutoff=0.85)
                if fuzzy_dist_matches: target_dist = fuzzy_dist_matches[0]

            if target_dist:
                for city in self.district_reverse_map[target_dist]:
                    found_districts.add((city, target_dist))
                    found_cities.add(city)

            # C. Check Neighborhood (Exact or Manual Hints)
            # Check manual neighborhoods first (High priority)
            if term in self.manual_neighborhoods:
                for city, dist in self.manual_neighborhoods[term]:
                    neighborhood_hints.append(f"{term} -> {city}/{dist}")
                    found_cities.add(city)
                    found_districts.add((city, dist))

            # Check from data registry
            elif term in self.neighborhood_map:
                for city, dist in self.neighborhood_map[term]:
                    neighborhood_hints.append(f"{term} -> {city}/{dist}")
                    found_cities.add(city)
                    found_districts.add((city, dist))

        if not found_cities and not found_districts:
            return "No specific location matches found in the registry for these tokens."

        # Format context
        ctx = "OFFICIAL LOCATION REGISTRY FOR THIS MESSAGE (Use these official names):\n"
        for city in sorted(list(found_cities)):
            all_dists = sorted(list(self.city_map.get(city, [])))
            ctx += f"- {city} Districts: {', '.join(all_dists)}\n"
            
        if neighborhood_hints:
            ctx += "\nNEIGHBORHOOD TO DISTRICT MAPPING:\n"
            ctx += "\n".join(sorted(list(set(neighborhood_hints))))
            
        return ctx

    def _fuzzy_match_city(self, candidate: str) -> Optional[str]:
        if len(candidate) < 3: return None
        import difflib
        matches = difflib.get_close_matches(candidate, self.city_map.keys(), n=1, cutoff=0.8)
        return matches[0] if matches else None

    def _fuzzy_match_district(self, candidate: str, possibilities: set) -> Optional[str]:
        if len(candidate) < 3: return None
        import difflib
        matches = difflib.get_close_matches(candidate, list(possibilities), n=1, cutoff=0.8)
        return matches[0] if matches else None

    def _fuzzy_match_district_global(self, candidate: str) -> Optional[str]:
        if len(candidate) < 3: return None
        import difflib
        matches = difflib.get_close_matches(candidate, self.district_reverse_map.keys(), n=1, cutoff=0.85)
        return matches[0] if matches else None

        return matches[0] if matches else None
