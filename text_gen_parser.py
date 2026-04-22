#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
STANDALONE TEXT GENERATION PARSER
Asynchronous and Parallel implementation using Groq (Llama 3.1)
Optimized with Concurrency Control (Semaphore) to prevent Rate Limits.
"""

import sys
import os
import json
import re
import logging
import asyncio
import time
import random
from typing import List, Dict, Any

from src.utils.file_operations import save_json_safe, load_json_safe
from src.services.persistence_manager import persistence_manager
from src.utils.api_key_manager import get_default_manager

# Logging setup
logger = logging.getLogger(__name__)

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

from groq import AsyncGroq, Groq

# Import validators
from src.utils.vehicle_type_matcher import VehicleTypeMatcher
from src.utils.city_district_validator import CityDistrictValidator

class TextGenParser:
    """Async/Parallel Groq (Llama 3.1) based parser with Traffic Control."""
    
    def __init__(self, api_key=None, max_concurrent=2):
        # Initialize API Key Manager for rotation
        self.key_manager = get_default_manager(os.getcwd())
        self.key_manager.load_keys()
        
        # Initialize validators
        self.vehicle_matcher = VehicleTypeMatcher()
        self.city_validator = CityDistrictValidator()
        
        # Traffic Control: Limit concurrent API calls to stay within TPM/RPM limits
        self.semaphore = asyncio.Semaphore(max_concurrent)
        
        # Models
        self.model_fast = 'llama-3.1-8b-instant'
        self.model_robust = 'llama-3.3-70b-versatile'
        self.fallback_models = ['mixtral-8x7b-32768', 'llama-3.1-70b-versatile'] # Keep decommed as secondary fallback just in case of regional availability
        
        # NEIGHBORHOOD CACHE
        self.neighborhood_cache = {}
        self._load_cache()

    def _get_async_client(self):
        """Returns an AsyncGroq client with a rotated API key."""
        api_key = self.key_manager.get_active_key()
        return AsyncGroq(api_key=api_key)

    def _get_client(self):
        """Synchronous client for legacy methods."""
        api_key = self.key_manager.get_active_key()
        return Groq(api_key=api_key)

    def _load_cache(self):
        cache_path = os.path.join(os.getcwd(), 'data', 'neighborhood_cache.json')
        self.neighborhood_cache = load_json_safe(cache_path, default={})

    def _save_cache(self):
        cache_path = os.path.join(os.getcwd(), 'data', 'neighborhood_cache.json')
        persistence_manager.queue_write(cache_path, self.neighborhood_cache)

    def _get_model_for_message(self, message: str) -> str:
        """Determines which model to use based on message complexity."""
        if len(message) < 150:
            return self.model_fast
        return self.model_robust

    async def _extract_locations_stage1_async(self, message: str) -> str:
        """Stage 1: Fast extraction of just origins and destinations (Async)."""
        system_prompt = "You are a location extractor. Output only the logical routes found in the message in 'ORIGIN -> DESTINATION' format."
        user_prompt = f"Extract routes from this logistics message:\n{message}"
        
        async with self.semaphore:
            try:
                client = self._get_async_client()
                response = await client.chat.completions.create(
                    model=self.model_fast,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    temperature=0.0
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"Stage 1 Async failed: {str(e)[:100]}")
                return ""

    async def parse_async(self, message: str) -> list:
        """Asynchronously parse logistics message with full logic recovery."""
        
        # 1. Context Preparation
        relevant_rules = self.vehicle_matcher.get_relevant_rules(message)
        rules_context = ""
        if relevant_rules:
            rules_context = "\n\nCRITICAL VEHICLE/LOAD TYPE RULES:\n"
            for rule in relevant_rules:
                out = rule['output']
                rules_context += f"- If '{rule['pattern']}': Set arac_tipi={out.get('ARAÇ TİPİ')}, kasa_tipi={out.get('KASA TİPİ')}\n"
        
        loc_context = self.city_validator.get_loc_context(message)
        
        # 2. Stage 1 (Ground Truth)
        confirmed_locs = ""
        if len(message) > 150:
            confirmed_locs = await self._extract_locations_stage1_async(message)
        
        loc_guideline = f"\nCONFIRMED ROUTES (Priority):\n{confirmed_locs}\n" if confirmed_locs else ""

        # 3. Final Parse Call (Stage 2)
        target_model = self._get_model_for_message(message)
        
        system_prompt = """You are a Turkish logistics parsing expert. Output ONLY valid JSON.
CRITICAL: ONLY extract routes explicitly mentioned in the message. DO NOT hallucinate or imagine destinations not found in the text.
VALID TURKISH CITIES: ADANA, ADIYAMAN, AFYONKARAHİSAR, AĞRI, AKSARAY, AMASYA, ANKARA, ANTALYA, ARDAHAN, ARTVİN, AYDIN, BALIKESİR, BARTIN, BATMAN, BAYBURT, BİLECİK, BİNGÖL, BİTLİS, BOLU, BURDUR, BURSA, ÇANAKKALE, ÇANKIRI, ÇORUM, DENİZLİ, DİYARBAKIR, DÜZCE, EDİRNE, ELAZIĞ, ERZİNCAN, ERZURUM, ESKİŞEHİR, GAZİANTEP, GİRESUN, GÜMÜŞHANE, HAKKARİ, HATAY, IĞDIR, ISPARTA, MERSİN, İSTANBUL, İZMİR, KAHRAMANMARAŞ, KARABÜK, KARAMAN, KARS, KASTAMONU, KAYSERİ, KIRIKKALE, KIRKLARELİ, KIRŞEHİR, KİLİS, KOCAELİ, KONYA, KÜTAHYA, MALATYA, MANİSA, MARDİN, MUĞLA, MUŞ, NEVŞEHİR, NİĞDE, ORDU, OSMANİYE, RİZE, SAKARYA, SAMSUN, SİİRT, SİNOP, SİVAS, ŞANLIURFA, ŞIRNAK, TEKİRDAĞ, TOKAT, TRABZON, TUNCELİ, UŞAK, VAN, YALOVA, YOZGAT, ZONGULDAK."""

        user_prompt = f"""Extract ALL routes from this message. 
STRICT RULE: Only create json objects for routes explicitly stated. Do NOT invent locations.

{loc_guideline}

EXTRACTION RULES:
1. HARD HIERARCHY: City > District > Neighborhood. ALWAYS identify the CITY (İL) first. 
2. NO HALLUCINATION: If a location is not in the message, DO NOT add it.
3. SUFFIXES: -den/-dan = ORIGIN, -e/-a = DESTINATION.
4. MULTI-ROUTE: "X'den Y ve Z'ye" = (X->Y) and (X->Z). 
5. MANDATORY KEYS: "nereden_il", "nereden_ilce", "nereye_il", "nereye_ilce", "type".
6. AMBIGUITY: If a name could be both a City and a District (e.g. "AYDIN"), prioritize it as a CITY unless context clearly says otherwise.

{loc_context}
{rules_context}

MESSAGE TO PARSE:
{message.strip()}

Return ONLY a JSON object in this format: 
{{"akil_yurutme": "...", "routes": [{{ "nereden_il": "CITY", "nereden_ilce": "DISTRICT", "nereye_il": "CITY", "nereye_ilce": "DISTRICT", "type": "VEHICLE" }}]}}"""

        models_to_try = [target_model, self.model_robust, self.model_fast]
        models_to_try = list(dict.fromkeys(models_to_try))

        async with self.semaphore:
            for model_name in models_to_try:
                for attempt in range(3):
                    try:
                        client = self._get_async_client()
                        active_key = self.key_manager.get_active_key()
                        response = await client.chat.completions.create(
                            model=model_name,
                            messages=[
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.0,
                            response_format={"type": "json_object"}
                        )
                        text = response.choices[0].message.content.strip()
                        return await self._process_raw_json_async(text, message)
                    except Exception as e:
                        error_str = str(e)
                        if "429" in error_str or "401" in error_str:
                            await self.key_manager.switch_to_next_async(reason=f"Batch {model_name}")
                            await asyncio.sleep(1)
                            continue
                # If 3 attempts failed for this model, try next model
                continue
            
        return []

    async def parse_batch(self, messages: List[str]) -> List[List[Dict[str, Any]]]:
        """Processes multiple messages in parallel using asyncio.gather."""
        tasks = [self.parse_async(msg) for msg in messages]
        return await asyncio.gather(*tasks)

    # LEGACY SYNC WRAPPER
    def parse(self, message: str) -> list:
        try:
            return asyncio.run(self.parse_async(message))
        except:
            import nest_asyncio
            nest_asyncio.apply()
            return asyncio.get_event_loop().run_until_complete(self.parse_async(message))

    async def _process_raw_json_async(self, text, message):
        """Processes raw JSON into validated routes (Async version)."""
        try:
            data = json.loads(text)
        except:
            json_match = re.search(r'\{.*\}|\[.*\]', text, re.DOTALL)
            data = json.loads(json_match.group()) if json_match else {"routes": []}
        
        raw_routes = data.get('routes', [])
        final_routes = []
        
        # Global phone extraction
        phone_match = re.search(r"(0\s*5\d{2}[\s\.\-\(\)]*\d{3}[\s\.\-\(\)]*\d{2}[\s\.\-\(\)]*\d{2})", message)
        default_phone = re.sub(r'\D', '', phone_match.group(1)) if phone_match else ""
        global_type_match = self.vehicle_matcher.find_match(message, per_route=False)
        
        for r in raw_routes:
            # Validate cities/districts via local registry
            origin_il, origin_ilce = self.city_validator.validate(r.get('nereden_il', ''), r.get('nereden_ilce', ''))
            dest_il, dest_ilce = self.city_validator.validate(r.get('nereye_il', ''), r.get('nereye_ilce', ''))
            
            # Neighborhood fallback (Async)
            if not origin_ilce and r.get('nereden_ilce'):
                origin_il, origin_ilce = await self._resolve_neighborhood_async(r.get('nereden_ilce'), r.get('nereden_il', ''))
            if not dest_ilce and r.get('nereye_ilce'):
                dest_il, dest_ilce = await self._resolve_neighborhood_async(r.get('nereye_ilce'), r.get('nereye_il', ''))

            # Re-validate after neighborhood fallback
            origin_il, origin_ilce = self.city_validator.validate(origin_il, origin_ilce)
            dest_il, dest_ilce = self.city_validator.validate(dest_il, dest_ilce)

            route_context = f"{r.get('nereden_il', '')} {r.get('nereye_il', '')} {r.get('type', '')}"
            type_match = self.vehicle_matcher.find_match(route_context, per_route=True) or global_type_match
            
            if type_match:
                arac_tipi = [type_match.get('ARAÇ TİPİ', '1360')]
                kasa_tipi = [k.strip() for k in type_match.get('KASA TİPİ', 'AÇIK KAPALI').split('+')]
                yuk_tipi = [type_match.get('YÜKÜN TİPİ', 'KOMPLE')]
            else:
                arac_tipi, kasa_tipi, yuk_tipi = ['1360'], ['AÇIK KAPALI'], ['KOMPLE']
            
            route = {
                "isim": "",
                "nereden_il": origin_il, "nereden_ilce": origin_ilce,
                "nereye_il": dest_il, "nereye_ilce": dest_ilce,
                "arac_tipi": arac_tipi, "kasa_tipi": kasa_tipi, "yuk_tipi": yuk_tipi,
                "fiyat": "SORUNUZ",  # Always default to 'SORUNUZ' as per user request
                "telefon": default_phone,
                "aciklama": message, "orijinal_mesaj": message
            }
            # Special pallet logic
            pallet_match = re.search(r"(\d+)\s*palet", message.lower())
            if pallet_match:
                try:
                    count = int(pallet_match.group(1))
                    route['yuk_tipi'] = ["PARÇA"] if 1 <= count <= 7 else ["KOMPLE"]
                except: pass
                
            final_routes.append(route)
            
        return final_routes

    async def _resolve_neighborhood_async(self, term: str, context_city: str = "") -> tuple:
        """Attempts to resolve neighborhood using AI (Async version)."""
        cache_key = f"{term.upper().strip()}|{context_city.upper().strip()}"
        if cache_key in self.neighborhood_cache:
            res = self.neighborhood_cache[cache_key]
            return tuple(res) if res else ("", "")

        async with self.semaphore:
            try:
                client = self._get_async_client()
                prompt = f"Target: Find TURKISH CITY/DISTRICT for '{term}'. Context: '{context_city}'. Output ONLY: CITY / DISTRICT"
                response = await client.chat.completions.create(
                    model=self.model_fast,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=20
                )
                text = response.choices[0].message.content.strip().upper()
                if "/" in text:
                    parts = text.split("/")
                    city, dist = parts[0].strip(), parts[1].strip()
                    self.neighborhood_cache[cache_key] = [city, dist]
                    self._save_cache()
                    return city, dist
            except: pass
        return "", ""

if __name__ == "__main__":
    parser = TextGenParser()
    test_msgs = ["ADANA - İZMİR TIR"]
    results = asyncio.run(parser.parse_batch(test_msgs))
    print(json.dumps(results, ensure_ascii=False, indent=2))
