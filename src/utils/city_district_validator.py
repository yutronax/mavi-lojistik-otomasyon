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
            "MKEMALPAŞA": "MUSTAFAKEMALPAŞA",
            "MUSTAFAKEMALPAŞA": "MUSTAFAKEMALPAŞA",
            "KPASA": "KEMALPAŞA",
            "KEMALPAŞA": "KEMALPAŞA",
            "İKEMALPAŞA": "KEMALPAŞA",
            "KEREĞLİ": "EREĞLİ",
            "ZEREĞLİ": "KARADENİZ EREĞLİ",
            "EREGLI": "EREĞLİ",
            "MEREĞLİ": "MARMARAEREĞLİSİ",
            "YKASABA": "TURGUTLU",
            "SERİNYOL": "ANTAKYA",
            "TEPECEK": "BÜYÜKÇEKMECE",
            "KÇEKMECE": "KÜÇÜKÇEKMECE",
            "BÇEKMECE": "BÜYÜKÇEKMECE",
            "KBAKKALKÖY": "ATAŞEHİR",
            "İKAYALAR": "MENDERES",
            "AVRUPA": "AVCILAR",
            "AVRUPA YAKASI": "AVCILAR",
            "AVRUPAYAKASI": "AVCILAR",
            "ANADOLU": "MALTEPE",
            "ANADOLU YAKASI": "MALTEPE",
            "ANADOLUYAKASI": "MALTEPE"
        }
        
        # City Alias Map (Yaygın kısaltmalar -> Resmi isimler)
        self.city_aliases = {
            "MARAŞ": "KAHRAMANMARAŞ",
            "KMARAŞ": "KAHRAMANMARAŞ",
            "ANTEP": "GAZİANTEP",
            "GANTEP": "GAZİANTEP",
            "URFA": "ŞANLIURFA",
            "ŞURFA": "ŞANLIURFA",
            "YAMAN": "ADIYAMAN",
            "ELAZIĞ": "ELAZIĞ", 
            "AFYON": "AFYONKARAHİSAR",
            "İÇEL": "MERSİN",
            "İST": "İSTANBUL",
            "İZM": "İZMİR",
            "ANK": "ANKARA",
            "KOC": "KOCAELİ",
            "SAK": "SAKARYA",
            "BUR": "BURSA"
        }
        
        # Neighborhood manually injected (Stratejik eksik bölgeler)
        self.manual_neighborhoods = {
            "SİTELER": [("ANKARA", "ALTINDAĞ")],
            "EREĞLİ": [("ZONGULDAK", "KARADENİZ EREĞLİ")],
            "OVACIK": [("ANKARA", "KEÇİÖREN")],
            "VEZİRHAN": [("BİLECİK", "MERKEZ")],
            "KEMALPAŞA": [("İZMİR", "KEMALPAŞA"), ("BURSA", "MUSTAFAKEMALPAŞA"), ("İSTANBUL", "BAĞCILAR")],
            "K.PAŞA": [("İZMİR", "KEMALPAŞA")],
            "İ.KEMALPAŞA": [("İZMİR", "KEMALPAŞA")],
            "TEMELLİ": [("ANKARA", "SİNCAN")],
            "HADIMKÖY": [("İSTANBUL", "ARNAVUTKÖY")],
            "TOPKAPI": [("İSTANBUL", "FATİH")],
            "İSTOÇ": [("İSTANBUL", "BAĞCILAR")],
            "İMRAHOR": [("İSTANBUL", "ARNAVUTKÖY")],
            "KEMERBURGAZ": [("İSTANBUL", "EYÜPSULTAN")],
            "GÜRPINAR": [("İSTANBUL", "BEYLİKDÜZÜ")],
            "KIRAÇ": [("İSTANBUL", "ESENYURT")],
            "DUDULLU": [("İSTANBUL", "ÜMRANİYE")],
            "GEBZE": [("KOCAELİ", "GEBZE")], 
            "ÇORLU": [("TEKİRDAĞ", "ÇORLU")],
            "İNEGÖL": [("BURSA", "İNEGÖL")],
            "İSKENDERUN": [("HATAY", "İSKENDERUN")],
            "TEPESİDELİK": [("KIRŞEHİR", "MERKEZ")]
        }
        
        self._load_data()

    def _normalize(self, text: str) -> str:
        """
        Turkish normalization: ensures i -> İ and ı -> I.
        Also strips punctuation and spaces for robust matching.
        """
        if not text:
            return ""
        
        # 0. Strip punctuation (BUT KEEP WHITESPACE)
        import re
        text = re.sub(r'[\.\,\'\"\-\(\)\:]+', '', text)
        
        # 1. Manual Turkish Uppercase (Robust)
        # Avoids combining characters by explicitly mapping common forms
        text = text.replace('i', 'İ').replace('ı', 'I')
        res = ""
        for char in text:
            if char == 'i': res += 'İ'
            elif char == 'ı': res += 'I'
            elif char == 'ç': res += 'Ç'
            elif char == 'ğ': res += 'Ğ'
            elif char == 'ö': res += 'Ö'
            elif char == 'ş': res += 'Ş'
            elif char == 'ü': res += 'Ü'
            else: res += char.upper()
            
        # 2. Cleanup Unicode artifacts (especially the combining dot above I)
        import unicodedata
        res = unicodedata.normalize('NFC', res)
        res = res.replace('\u0307', '') # Strip combining dot above if any remains
        
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

            # Inject manual neighborhoods
            for m_name, locs in self.manual_neighborhoods.items():
                m_norm = self._normalize(m_name)
                if m_norm not in self.neighborhood_map:
                    self.neighborhood_map[m_norm] = []
                for city, dist in locs:
                    c_norm, d_norm = self._normalize(city), self._normalize(dist)
                    if (c_norm, d_norm) in self.neighborhood_map[m_norm]:
                        self.neighborhood_map[m_norm].remove((c_norm, d_norm))
                    self.neighborhood_map[m_norm].insert(0, (c_norm, d_norm))

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
            if "ANADOLU" in norm_dist: norm_dist = "MALTEPE"
            elif "AVRUPA" in norm_dist: norm_dist = "AVCILAR"
            elif forced_default: norm_dist = forced_default
        
        # Ignore numeric districts (e.g. "2" from "2 NOKTA")
        if norm_dist and norm_dist.isdigit():
            norm_dist = ""

        if not norm_city and not norm_dist:
            return "", ""

        # --- TRAP LOCATIONS (Common Logistics Errors) ---
        if norm_city == "İSTANBUL" and norm_dist == "KEMALPAŞA":
            # In 99% of logistics messages, "İ. Kemalpaşa" means İzmir
            return "İZMİR", "KEMALPAŞA"
        
        if norm_city == "İSTANBUL" and norm_dist == "İKEMALPAŞA":
            return "İZMİR", "KEMALPAŞA"

        # --- STEP 1: PRECISE CITY MATCH (The "Hard" Filter) ---
        if norm_city in self.city_map:
            valid_dists = self.city_map[norm_city]
            
            # A. Check if input is directly a district in this city
            if norm_dist in valid_dists:
                return norm_city, norm_dist
            
            # Special case: If user says 'MERKEZ', prioritize city default over neighborhoods named 'MERKEZ'
            if norm_dist == "MERKEZ" and norm_city in self.default_districts:
                return norm_city, self.default_districts[norm_city]
            
            # B. Check if input is a neighborhood/village in this city
            if norm_dist in self.neighborhood_map:
                for c, d in self.neighborhood_map[norm_dist]:
                    if c == norm_city:
                        return c, d
            
            # D. If it's a neighborhood but NOT in this city, maybe the city is wrong?
            # We don't return here yet, we let Step 2-4 try to find it elsewhere.
            pass

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

        # --- STEP 6: FINAL FALLBACK ---
        if norm_city in self.city_map:
            return norm_city, self.default_districts.get(norm_city, 'MERKEZ')

        return norm_city or "BİLİNMEYEN", norm_dist or "MERKEZ"

    def get_loc_context(self, message: str) -> str:
        """
        Scans message for keywords and returns relevant official location registry.
        Supports Aliases (Maraş, Urfa) and Fuzzy matches for typos.
        """
        if not message:
            return ""
            
        # 1. Normalize carefully for Turkish
        norm_msg = self._normalize(message)
        
        # 2. Tokenize carefully (keep dots for abbreviations)
        # Use a more robust split that handles Turkish characters better than \b in some environments
        # First remove non-alphanumeric (keep spaces and dots)
        clean_msg = re.sub(r'[^\w\s\.]', ' ', norm_msg)
        tokens = clean_msg.split()
        # Search space includes single tokens and pairs (for multi-word locations)
        search_space = tokens + [" ".join(tokens[i:i+2]) for i in range(len(tokens)-1)]
        
        found_cities = set()
        found_districts = set() # (City, Dist)
        neighborhood_hints = []
        
        valid_cities_list = list(self.city_map.keys())
        valid_districts_list = list(self.district_reverse_map.keys())

        import difflib

        for raw_term in search_space:
            # Normalize for comparison (remove dots etc)
            term = self._normalize(raw_term)
            if not term: continue
            
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
