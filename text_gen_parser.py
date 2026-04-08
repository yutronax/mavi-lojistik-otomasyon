#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STANDALONE TEXT GENERATION PARSER
Clean implementation using Gemini text generation (not structured output)
Includes VehicleTypeMatcher and CityDistrictValidator integration
"""

import sys
import os
import json
import re
from src.utils.file_operations import save_json_safe, load_json_safe
from src.services.persistence_manager import persistence_manager

# Fix Windows encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

sys.path.insert(0, os.getcwd())

from dotenv import load_dotenv
load_dotenv()

import google.generativeai as genai

# Import validators
from src.utils.vehicle_type_matcher import VehicleTypeMatcher
from src.utils.city_district_validator import CityDistrictValidator

class TextGenParser:
    """Gemini Text Generation based parser - production ready."""
    
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        genai.configure(api_key=self.api_key, transport='rest')
        
        # Initialize validators
        self.vehicle_matcher = VehicleTypeMatcher()
        self.city_validator = CityDistrictValidator()
        
        # Models to try in order
        self.primary_model = 'gemini-2.0-flash'
        self.fallback_models = ['gemini-1.5-flash', 'gemini-1.5-flash-8b']
        
        # NEIGHBORHOOD CACHE: To prevent redundant LLM calls for the same place/district
        # Maps "TERM|CONTEXT_CITY" -> (Resolved City, Resolved District)
        self.neighborhood_cache = {}
        self._load_cache()

    def _load_cache(self):
        """Loads neighborhood cache from file if exists."""
        cache_path = os.path.join(os.getcwd(), 'data', 'neighborhood_cache.json')
        self.neighborhood_cache = load_json_safe(cache_path, default={})

    def _save_cache(self):
        """Saves neighborhood cache to file."""
        cache_path = os.path.join(os.getcwd(), 'data', 'neighborhood_cache.json')
        # Arka planda güvenli ve kilitlenmeyen yazma
        persistence_manager.queue_write(cache_path, self.neighborhood_cache)
    
    def parse(self, message: str) -> list:
        """Parse logistics message using text generation."""
        
        # 1. Get dynamic rules based on message content
        relevant_rules = self.vehicle_matcher.get_relevant_rules(message)
        rules_context = ""
        if relevant_rules:
            rules_context = "\n\nCRITICAL VEHICLE/LOAD TYPE RULES FOR THIS MESSAGE:\n"
            for i, rule in enumerate(relevant_rules, 1):
                out = rule['output']
                rules_context += f"- If message contains '{rule['pattern']}': Set arac_tipi={out.get('ARAÇ TİPİ')}, kasa_tipi={out.get('KASA TİPİ')}, yuk_tipi={out.get('YÜKÜN TİPİ')}\n"
            rules_context += "(Priority: These rules override your general knowledge)\n"

        # Comprehensive prompt covering ALL 3 formats
        prompt = f"""You are a Turkish logistics message parsing expert. Extract ALL routes from this message.

CRITICAL: There are 3 PRIMARY MESSAGE FORMATS:

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT 1: LOAD ANNOUNCEMENT (Yük İlanı)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern: Origin mentioned in first line, destinations in subsequent lines

Example 1:
"Bursa Mustafakemalpaşa hemen yükleme
Esenyurt+Eyüp tır"

Interpretation:
- Origin: BURSA/MUSTAFAKEMALPAŞA (looking for loads)
- Destinations: İSTANBUL/ESENYURT, İSTANBUL/EYÜP
- Creates 2 routes, BOTH from BURSA:
  * BURSA/MUSTAFAKEMALPAŞA → İSTANBUL/ESENYURT
  * BURSA/MUSTAFAKEMALPAŞA → İSTANBUL/EYÜP

Example 2:
"*Bursa* *Mustafakemalpaşa* *yükler*

Düzce+kartal+tuzla /TİR

Uşak+Serik tır

Serik+Alanya 10 teker"

Interpretation:
- Line 1: "*yükler*" = load announcement, origin = BURSA/MUSTAFAKEMALPAŞA
- Line 2: "Düzce+kartal+tuzla" = 3 destinations (DÜZCE/MERKEZ, İSTANBUL/KARTAL, İSTANBUL/TUZLA)
  → Creates 3 routes ALL from BURSA/MUSTAFAKEMALPAŞA
- Line 3: "Uşak+Serik" = NEW independent route UŞAK/MERKEZ → ANTALYA/SERİK
- Line 4: "Serik+Alanya" = NEW independent route ANTALYA/SERİK → ANTALYA/ALANYA
- Total: 5 routes

Key indicators: "yükler", "yük", "hemen yükleme", "yük aranıyor", "boş araç"
CRITICAL: If first line has "yükler" or similar, it's the origin for ALL destinations in the NEXT line!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT 1.5: GLOBAL ORIGIN HEADER (BAŞLIK ETKİSİ)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern: Message STARTS with a clear Origin (e.g. "XXX'DEN", "XXX BÖLGESİNDEN"), followed by list of loads.

Example:
"KIZILTEPEDEN✅✅
MALATYAYA MISIR 🌽 
KISA DORSA  

ADANA KARATAŞ MISIR 🌽 
KISA DORSA ✅

CEYHAN MISIR"

Interpretation:
- Line 1: "KIZILTEPEDEN" -> Global Origin = MARDİN/KIZILTEPE
- Item 1: "MALATYAYA" -> Route: MARDİN/KIZILTEPE → MALATYA/MERKEZ
- Item 2: "ADANA KARATAŞ" -> Route: MARDİN/KIZILTEPE → ADANA/KARATAŞ
- Item 3: "CEYHAN" -> Route: MARDİN/KIZILTEPE → ADANA/CEYHAN

CRITICAL: Look for suffix "-DEN/-DAN" or words "ÇIKIŞLI", "YÜKLENEN" at the very top.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT 2: LINE-BY-LINE ROUTES (Satır Satır)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern: Each line is complete origin→destination pair

Example:
"İSTANBUL PENDİK - ANKARA MERKEZ
MERSİN - İZMİR TIRE
GAZİANTEP - DİYARBAKIR"

Interpretation:
- 3 SEPARATE routes
- Line 1 origin ≠ Line 2 origin ≠ Line 3 origin
- Each line is independent

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FORMAT 3: SINGLE SENTENCE MULTI-ROUTE (Tek Cümle)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Pattern: One origin, multiple destinations with operators

Example:
"BURSA - ANKARA + İZMİR + ADANA KAPALI TIR"

Interpretation:
- Operators: '+', '&', 'VE', ','
- Same origin, multiple destinations
- Creates 3 routes, ALL from BURSA:
  * BURSA/MERKEZ → ANKARA/MERKEZ
  * BURSA/MERKEZ → İZMİR/MERKEZ
  * BURSA/MERKEZ → ADANA/MERKEZ

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

ADDITIONAL RULES:

1. **LOCATION RESOLUTION & HIERARCHY (CRITICAL)**:
   You must resolve locations using this EXACT 5-step hierarchy:

   A) **City + District Found**:
      - Use both. (e.g. "Ankara Etimesgut" -> City: Ankara, District: Etimesgut)

   B) **City Found, No District**:
      - Use City. District = "" (Empty). 
      - (System will assign default district later).

   C) **City + Neighborhood Found**:
      - Use City. Match Neighborhood to find correct District.
      - e.g. "İstanbul Kozyatağı" -> Start with İstanbul -> Find Kozyatağı is in Kadıköy -> Output: İstanbul / Kadıköy.
      - **CRITICAL**: Do NOT output the neighborhood name as district. Output the DISTRICT it belongs to.

   D) **No City, District Found**:
      - Infer City from District.
      - e.g. "Gebze" -> Infer Kocaeli -> Output: Kocaeli / Gebze.
      - e.g. "Alanya" -> Infer Antalya -> Output: Antalya / Alanya.

   E) **No City, No District, Only Neighborhood/Place**:
      - Search for the Neighborhood/Place unique name.
      - Infer District AND City.
      - e.g. "İkitelli" -> Infer Başakşehir / İstanbul.
      - e.g. "Ostim" -> Infer Yenimahalle / Ankara.
      - e.g. "Saray" (Kazan) -> Infer Kahramankazan / Ankara.

   - **General Rule**: Use your knowledge base to map Neighborhoods/Popular Places -> District -> City.

3. **COMMON PITFALLS (DO NOT CONFUSE)**:
   - **HADIMKÖY (Arnavutköy/Esenyurt side)** is NOT **KADIKÖY (Anatolian side)**.
   - If message says "Hadımköy", DO NOT output "Kadıköy".
   - If message says "Gebze", it's Kocaeli, NOT Istanbul.
   - If message says "Çorlu", it's Tekirdağ, NOT Istanbul.

4. **REQUIRED FIELDS**:
   - Every route MUST have: nereden_il, nereden_ilce, nereye_il, nereye_ilce
   - NEVER leave any field empty!

   - Extract vehicle/body/load type as-is (e.g., "TIR BRANDALI")
   - Post-processing will normalize

5. **NO HALLUCINATIONS (STRICT)**:
   - Do NOT change the City if the user explicitly wrote one (e.g. "Bursa Akçalar" -> Origin MUST be BURSA).
   - Do NOT guess a District (e.g. "Akçalar" -> "Adalar" is WRONG). If you don't know the district, leave it blank or put the village name.
   - It is better to output "BURSA / AKÇALAR" (which our validator will handle) than to hallucinate "İSTANBUL / ADALAR".
{rules_context}
MESSAGE TO PARSE:
{message.strip()}

Return ONLY valid JSON (NO markdown, NO explanation). Ensure strict JSON format (commas between fields!):
{{"routes": [
  {{
    "nereden_il": "CITY",
    "nereden_ilce": "DISTRICT",
    "nereye_il": "CITY",
    "nereye_ilce": "DISTRICT",
    "type": "VEHICLE/BODY/LOAD TYPE",
    "fiyat": "PRICE (e.g. 15000 TL) OR 'SORUNUZ'"
  }}
]}}"""

        # Retry logic with backoff
        import time
        import random
        
        models_to_try = [self.primary_model] + self.fallback_models
        last_error = None
        
        for model_name in models_to_try:
            for attempt in range(3):
                try:
                    model = genai.GenerativeModel(model_name=model_name)
                    response = model.generate_content(
                        prompt,
                        generation_config={"temperature": 0.0}
                    )
                    
                    # Clean and parse
                    text = response.text.strip()
                    text = text.replace('```json', '').replace('```', '').strip()
                    
                    # DEBUG: Raw LLM output
                    print(f"DEBUG RAW LLM: {text}")
                    return self._process_raw_json(text, message)
                    
                except Exception as e:
                    last_error = e
                    err_str = str(e).lower()
                    
                    if "429" in err_str or "quota" in err_str:
                        wait_time = (2 ** attempt) + random.random()
                        print(f"[RETRY] Model {model_name} rate limited (attempt {attempt+1}/3). Waiting {wait_time:.2f}s...")
                        time.sleep(wait_time)
                        continue
                    else:
                        # Other errors (e.g. 400 Bad Request, blockages), move to next model
                        print(f"[ERROR] Model {model_name} failed: {e}")
                        break
            
            print(f"[SWITCH] Model {model_name} failed or exhausted. Trying next fallback...")
            
        print(f"Parse error: All models failed. Last error: {last_error}")
        return []

    def _process_raw_json(self, text, message):
        """Helper to process raw JSON text into final route objects."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Attempt 1: Fix common errors (missing commas, unescaped newlines)
            # 1. Replace real newlines with spaces (JSON values shouldn't have real line breaks)
            clean_text = text.replace('\n', ' ')
            # 2. Fix missing commas between string fields like "Value" "Key"
            clean_text = re.sub(r'"\s+"', '", "', clean_text)
            
            try:
                data = json.loads(clean_text)
            except json.JSONDecodeError:
                # Attempt 2: Extract JSON object/array if embedded in text
                json_match = re.search(r'\{.*\}|\[.*\]', text, re.DOTALL)
                if json_match:
                    try:
                        chunk = json_match.group()
                        # Apply same cleaning to chunk
                        chunk_clean = chunk.replace('\n', ' ')
                        chunk_clean = re.sub(r'"\s+"', '", "', chunk_clean)
                        data = json.loads(chunk_clean)
                    except json.JSONDecodeError:
                         print(f"[ERROR] Failed to parse JSON. Raw text:\n{text}")
                         data = {"routes": []}
                else:
                    print(f"[ERROR] No JSON found in response. Raw text:\n{text}")
                    data = {"routes": []}
        
        raw_routes = data.get('routes', [])
        
        # Post-process each route
        final_routes = []
        
        # Extract global defaults (phone, price, global types)
        phone_match = re.search(r"(0\s*5\d{2}[\s\.\-\(\)]*\d{3}[\s\.\-\(\)]*\d{2}[\s\.\-\(\)]*\d{2})", message)
        if phone_match:
            # Clean phone: keep only digits
            default_phone = re.sub(r'\D', '', phone_match.group(1))
        else:
            default_phone = ""
        
        # Try global type matching once (as fallback)
        global_type_match = self.vehicle_matcher.find_match(message, per_route=False)
        
        # SANITY CHECK: Identify all mentioned cities in the message
        mentioned_cities = set()
        norm_message = self.city_validator._normalize(message)
        
        for city in self.city_validator.city_map.keys():
            if city in norm_message:
                mentioned_cities.add(city)
        
        for r in raw_routes:
            # Capture pre-validation state
            pre_orig_il = self.city_validator._normalize(r.get('nereden_il', ''))
            pre_dest_il = self.city_validator._normalize(r.get('nereye_il', ''))
            
            # 1. City/District validation
            origin_il, origin_ilce = self.city_validator.validate(
                r.get('nereden_il', ''),
                r.get('nereden_ilce', '')
            )
            
            dest_il, dest_ilce = self.city_validator.validate(
                r.get('nereye_il', ''),
                r.get('nereye_ilce', '')
            )
            
            # HALLUCINATION GUARD: If validation flipped city to something NOT in text
            if pre_orig_il in mentioned_cities and origin_il != pre_orig_il:
                 if origin_il not in mentioned_cities:
                     # Revert to original city
                     origin_il = pre_orig_il
                     # Re-validate with EMPTY district to trigger Default District logic (e.g. Ankara -> Yenimahalle)
                     _, origin_ilce = self.city_validator.validate(origin_il, "")
                     r['nereden_ilce'] = origin_ilce

            if pre_dest_il in mentioned_cities and dest_il != pre_dest_il:
                 if dest_il not in mentioned_cities:
                     dest_il = pre_dest_il
                     _, dest_ilce = self.city_validator.validate(dest_il, "")
                     r['nereye_ilce'] = dest_ilce

            # 2. RECOVERY: If district became empty but was originally provided, try neighborhood resolution
            orig_ilce = r.get('nereden_ilce')
            if not origin_ilce and orig_ilce and str(orig_ilce).strip():
                raw_term = str(orig_ilce).strip()
                if len(raw_term) > 2:
                   rec_il, rec_ilce = self._resolve_neighborhood(raw_term, r.get('nereden_il', ''))
                   if rec_ilce:
                       origin_il, origin_ilce = rec_il, rec_ilce
                       r['nereden_il'], r['nereden_ilce'] = origin_il, origin_ilce
            
            orig_dest_ilce = r.get('nereye_ilce')
            if not dest_ilce and orig_dest_ilce and str(orig_dest_ilce).strip():
                raw_term = str(orig_dest_ilce).strip()
                if len(raw_term) > 2:
                   rec_il, rec_ilce = self._resolve_neighborhood(raw_term, r.get('nereye_il', ''))
                   if rec_ilce:
                       dest_il, dest_ilce = rec_il, rec_ilce
                       r['nereye_il'], r['nereye_ilce'] = dest_il, dest_ilce
            
            # 2. Per-route type matching
            route_context = f"{r.get('nereden_il', '')} {r.get('nereye_il', '')} {r.get('type', '')}"
            per_route_match = self.vehicle_matcher.find_match(route_context, per_route=True)
            
            type_match = per_route_match if per_route_match else global_type_match
            
            if type_match:
                arac_tipi = [type_match.get('ARAÇ TİPİ', '1360')]
                kasa_tipi_raw = type_match.get('KASA TİPİ', 'AÇIK KAPALI')
                yuk_tipi_raw = type_match.get('YÜKÜN TİPİ', 'KOMPLE')
                
                if '+' in kasa_tipi_raw:
                    kasa_tipi = [k.strip() for k in kasa_tipi_raw.split('+')]
                else:
                    kasa_tipi = [kasa_tipi_raw]
                
                yuk_tipi = [yuk_tipi_raw]
            else:
                arac_tipi = ['1360']
                kasa_tipi = ['AÇIK KAPALI']
                yuk_tipi = ['KOMPLE']
            
            route = {
                "isim": "",
                "nereden_il": origin_il,
                "nereden_ilce": origin_ilce,
                "nereye_il": dest_il,
                "nereye_ilce": dest_ilce,
                "arac_tipi": arac_tipi,
                "kasa_tipi": kasa_tipi,
                "yuk_tipi": yuk_tipi,
                "fiyat": r.get('fiyat') or 'SORUNUZ',
                "telefon": default_phone,
                "aciklama": message,
                "orijinal_mesaj": message
            }
            
            # 4. DİNAMİK PALET DÜZELTMESİ (Hassas Kural)
            route = self._apply_dynamic_pallet_correction(message, route)
            
            final_routes.append(route)
        
        return final_routes
            

    def _resolve_neighborhood(self, term: str, context_city: str = "") -> tuple:
        """
        Attempts to resolve a generic term (neighborhood/village) to a City/District pair using AI.
        Returns (City, District) or ("", "") if failed.
        """
        # 1. Check Cache
        cache_key = f"{term.upper().strip()}|{context_city.upper().strip()}"
        if cache_key in self.neighborhood_cache:
            res = self.neighborhood_cache[cache_key]
            return tuple(res) if res else ("", "")

        # Use primary model for neighborhood resolution too
        import time
        import random
        
        models_to_try = [self.primary_model] + self.fallback_models
        
        for model_name in models_to_try:
            for attempt in range(2): # Fewer retries for neighborhood
                try:
                    model = genai.GenerativeModel(model_name=model_name)
                    
                    prompt = f"""Target: Find the official TURKISH CITY and DISTRICT for the place name "{term}".
        Context City: "{context_city}" (VERY IMPORTANT).
        
        Rules:
        1. Output ONLY in format: CITY / DISTRICT
        2. **PRIORITY RULE**: If "{term}" represents a location inside "{context_city}", YOU MUST OUTPUT "{context_city}". Only change the city if "{term}" is a well-known location COMPLETELY OUTSIDE "{context_city}".
        3. If "{term}" is a village or neighborhood in "{context_city}", find its connected District.
        4. If uncertain, output: UNKNOWN
        5. Example: "Ostim" (Context: Anka..) -> ANKARA / YENİMAHALLE
        6. Example: "Akçalar" (Context: Bursa) -> BURSA / NİLÜFER (Do not hallucinate İstanbul!)
        7. Example: "Konyaaltı" (Context: Ankara) -> ANTALYA / KONYAALTI (Valid city switch because Konyaaltı is unique to Antalya)
        
        Answer:"""
                    
                    response = model.generate_content(
                        prompt,
                        generation_config={"temperature": 0.0, "max_output_tokens": 20}
                    )
                    
                    text = response.text.strip().upper()
                    # Success - return parts
                    return self._process_neighborhood_response(text, term, context_city, cache_key)
                    
                except Exception as e:
                    err_str = str(e).lower()
                    if "429" in err_str or "quota" in err_str:
                        time.sleep(1 + random.random())
                        continue
                    else:
                        break
        
        return "", ""

    def _process_neighborhood_response(self, text, term, context_city, cache_key):
        """Processes AI response for neighborhood resolution."""
        if "UNKNOWN" in text:
            return "", ""
        
        if "/" in text:
            parts = text.split("/")
            if len(parts) >= 2:
                city = parts[0].strip()
                dist = parts[1].strip()
                
                # Validate the AI's hallucination against our DB
                val_city, val_dist = self.city_validator.validate(city, dist)
                if val_city and val_dist:
                    # CRITICAL HALLUCINATION GUARD
                    if context_city and val_city != self.city_validator._normalize(context_city):
                        norm_term = self.city_validator._normalize(term)
                        norm_dist = self.city_validator._normalize(val_dist)
                        
                        if norm_dist not in norm_term and norm_term not in norm_dist:
                            print(f"GUARD: Prevented hallucination {term} ({context_city}) -> {val_city}/{val_dist}")
                            return "", ""

                    # Save to cache
                    self.neighborhood_cache[cache_key] = [val_city, val_dist]
                    self._save_cache()
                    return val_city, val_dist
        
        # Negatif cache
        self.neighborhood_cache[cache_key] = ["", ""]
        self._save_cache()
        return "", ""
            
    def _apply_dynamic_pallet_correction(self, message: str, route: dict) -> dict:
        """
        Hassas Kural: 1-7 palet arası 'PARÇA', 7+ palet 'KOMPLE' olarak işaretlenir.
        Paletten hemen önceki sayıya bakılır.
        """
        # Regex: Sayı + opsiyonel boşluk + palet
        pallet_match = re.search(r"(\d+)\s*palet", message.lower())
        
        if pallet_match:
            try:
                count = int(pallet_match.group(1))
                if 1 <= count <= 7:
                    route['yuk_tipi'] = ["PARÇA"]
                    # Not ekle (Opsiyonel, takip için)
                    if "aciklama" in route:
                        route['aciklama'] = f"[OTOMATİK DÜZELTME: {count} palet <= 7 -> PARÇA] " + route['aciklama']
                elif count > 7:
                    route['yuk_tipi'] = ["KOMPLE"]
                    if "aciklama" in route:
                        route['aciklama'] = f"[OTOMATİK DÜZELTME: {count} palet > 7 -> KOMPLE] " + route['aciklama']
            except (ValueError, TypeError):
                pass
                
        return route
            


# TEST
if __name__ == "__main__":
    parser = TextGenParser()
    
    test_msg = """İSTANBUL PENDİK - ANKARA MERKEZ TIR BRANDALI 26 TON
MERSİN - İZMİR TIRE AÇIK 15 TON
GAZİANTEP - DİYARBAKIR KOMPLE"""
    
    print("=" * 80)
    print("TEXT GENERATION PARSER TEST")
    print("=" * 80)
    print(f"\n{test_msg}\n")
    print("-" * 80)
    
    results = parser.parse(test_msg)
    
    print(f"\n✓ Parsed {len(results)} routes\n")
    
    for i, r in enumerate(results, 1):
        print(f"[Route {i}]")
        print(f"  {r['nereden_il']}/{r['nereden_ilce']} → {r['nereye_il']}/{r['nereye_ilce']}")
        print(f"  Kasa: {', '.join(r['kasa_tipi'])}")
    
    # Validation
    print("\n" + "=" * 80)
    print("VALIDATION")
    print("=" * 80)
    
    check1 = len(results) == 3
    check2 = results[1]['nereden_il'] == 'MERSİN' if len(results) > 1 else False
    check3 = results[2]['nereden_il'] in ['GAZİANTEP', 'GAZIANTEP'] if len(results) > 2 else False
    
    print(f"{'✅' if check1 else '❌'} 3 routes")
    print(f"{'✅' if check2 else '❌'} Route 2 from MERSİN")
    print(f"{'✅' if check3 else '❌'} Route 3 from GAZİANTEP")
    
    if check1 and check2 and check3:
        print("\n🎉 PERFECT! Ready for production!")
        
        # Save results
        with open('standalone_parser_results.json', 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"📄 Results saved: standalone_parser_results.json")
