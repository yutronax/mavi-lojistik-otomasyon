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

    def _ascii_key(self, text: str) -> str:
        """Converts Turkish characters to ASCII equivalents for loose matching.
        Examples: İNEGÖL->INEGOL, GÜRSU->GURSU, ŞANLIURFA->SANLIURFA
        """
        if not text: return ""
        t = self._normalize(text)
        t = t.replace('İ', 'I').replace('Ö', 'O').replace('Ü', 'U')
        t = t.replace('Ş', 'S').replace('Ç', 'C').replace('Ğ', 'G')
        return t

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
            # ASCII-key -> (proper_city, proper_district) for loose matching
            self.ascii_district_index = {}

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

                    # ASCII-key index for loose (no special char) matching
                    akey = self._ascii_key(dist)
                    if akey not in self.ascii_district_index:
                        self.ascii_district_index[akey] = []
                    self.ascii_district_index[akey].append((city, dist))
                    
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
        1. Resolve City (Precise or Fuzzy)
        2. Resolve District within that City (Precise or High-Similarity Fuzzy)
        3. If no match, ignore district.
        """
        norm_city = self._normalize(city)
        norm_dist = self._normalize(district)
        
        # --- BLACKLIST TRAP (Do not even try to validate these as locations) ---
        # Covers Turkish char variants: ÖLÜR (for OLUR), GÜNÜ, etc.
        forbidden = {
            "HAFİF", "MADEN", "MERMER", "SOĞAN", "DEMİR", "KÖMÜR",
            "KARTON", "SUNTA", "BRANDA", "NAKLİYE", "NAK", "LOJİSTİK",
            "OLUR", "ÖLÜR", "GÜNÜ", "SAAT", "PARÇA", "PARCA", "TONAJ",
            "KADAR", "KAPASITE"
        }
        if norm_dist in forbidden: norm_dist = ""
        if norm_city in forbidden: norm_city = ""

        # Step 1: Resolve City (OR Check if city parameter is actually a district)
        resolved_city = None
        
        # A. If the 'city' provided is actually a district (Exact or Fuzzy), recover it!
        if norm_city and norm_city not in self.city_map:
            # First try EXACT match for district
            target_dist = None
            if norm_city in self.district_reverse_map:
                target_dist = norm_city
            else:
                # If no exact match, try FUZZY match across ALL districts in Turkey
                import difflib
                all_districts = list(self.district_reverse_map.keys())
                fuzzy_matches = difflib.get_close_matches(norm_city, all_districts, n=1, cutoff=0.90)
                if fuzzy_matches:
                    target_dist = fuzzy_matches[0]
            
            if target_dist:
                cities = self.district_reverse_map[target_dist]
                if len(cities) == 1:
                    resolved_city = cities[0]
                    norm_dist = target_dist
        
        # B. Normal City Resolve
        if not resolved_city:
            if norm_city in self.city_map:
                resolved_city = norm_city
            elif norm_city in self.city_aliases:
                resolved_city = self.city_aliases[norm_city]
            else:
                resolved_city = self._fuzzy_match_city(norm_city)

        # Step 2: Resolve District (Strict Hierarchy)
        if resolved_city:
            valid_dists = self.city_map[resolved_city]
            
            # A. Precise Match
            if norm_dist in valid_dists:
                return resolved_city, norm_dist
            
            # B. Precise Neighborhood Match in this City
            if norm_dist in self.neighborhood_map:
                for c, d in self.neighborhood_map[norm_dist]:
                    if c == resolved_city: return c, d

            # C. ASCII Loose Match (handles İnegol->İnegöl, Gursu->Gürsu)
            if norm_dist:
                dist_akey = self._ascii_key(norm_dist)
                if dist_akey in self.ascii_district_index:
                    for c, d in self.ascii_district_index[dist_akey]:
                        if c == resolved_city:
                            return resolved_city, d

            # D. High-Similarity Fuzzy Match (ONLY within this City)
            if norm_dist and len(norm_dist) > 3:
                import difflib
                matches = difflib.get_close_matches(norm_dist, list(valid_dists), n=1, cutoff=0.92)
                if matches:
                    return resolved_city, matches[0]

            # E. No match? Fall back to city default
            return resolved_city, self.default_districts.get(resolved_city, 'MERKEZ')

        # Step 3: No City found? Search District Globally (exact or ASCII-loose)
        if norm_dist and len(norm_dist) > 4:
            if norm_dist in self.district_reverse_map:
                cities = self.district_reverse_map[norm_dist]
                if len(cities) == 1: return cities[0], norm_dist
            # ASCII loose global search
            dist_akey = self._ascii_key(norm_dist)
            if dist_akey in self.ascii_district_index:
                candidates = self.ascii_district_index[dist_akey]
                if len(candidates) == 1:
                    return candidates[0]

        return resolved_city or "BİLİNMEYEN", "MERKEZ"

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
            # Find which districts of THIS city were actually in the message
            districts_in_msg = [d for c, d in found_districts if c == city]
            
            if districts_in_msg:
                # If we found specific districts, list them
                ctx += f"- {city} (Relevant Districts: {', '.join(sorted(districts_in_msg))})\n"
            else:
                # If only city was found, don't list all districts if there are too many
                all_dists = sorted(list(self.city_map.get(city, [])))
                if len(all_dists) > 10:
                    ctx += f"- {city} (City identified)\n"
                else:
                    ctx += f"- {city} Districts: {', '.join(all_dists)}\n"
            
        if neighborhood_hints:
            ctx += "\nNEIGHBORHOOD TO DISTRICT MAPPING:\n"
            # Limit neighborhood hints to avoid overflow
            limited_hints = sorted(list(set(neighborhood_hints)))[:20]
            ctx += "\n".join(limited_hints)
            
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
