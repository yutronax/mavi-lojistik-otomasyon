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
import threading
import time
import random
from typing import List, Dict, Any
from datetime import datetime

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
from openai import AsyncOpenAI
from google import genai as google_genai

# Import validators
from src.utils.vehicle_type_matcher import VehicleTypeMatcher
from src.utils.city_district_validator import CityDistrictValidator

class TextGenParser:
    """Async/Parallel Groq (Llama 3.1) based parser with Traffic Control."""
    
    def __init__(self, api_key=None, max_concurrent=1):
        # Initialize API Key Manager for rotation
        self.key_manager = get_default_manager(os.getcwd())
        self.key_manager.load_keys()
        
        # Initialize validators
        self.vehicle_matcher = VehicleTypeMatcher()
        self.city_validator = CityDistrictValidator()
        
        # Traffic Control: Limit concurrent API calls to stay within TPM/RPM limits
        # Using threading.Semaphore because we use ThreadPoolExecutor in Orchestrator
        self.semaphore = threading.Semaphore(max_concurrent)
        
        # Models - Using Llama as primary due to Gemini environment 404s
        self.model_fast = 'llama-3.1-8b-instant'
        self.model_robust = 'llama-3.3-70b-versatile'
        self.model_deepseek = 'deepseek-chat'
        self.model_gemini = 'llama-3.3-70b-versatile'
        self.fallback_models = ['mixtral-8x7b-32768', 'llama-3.1-70b-versatile']
        
        # NEIGHBORHOOD CACHE
        self.neighborhood_cache = {}
        self._load_cache()

    def _get_async_client(self):
        """Returns an AsyncGroq client with a rotated API key from the groq pool."""
        api_key = self.key_manager.get_active_key(key_type='groq')
        return AsyncGroq(api_key=api_key)

    def _get_deepseek_client(self):
        """Returns an AsyncOpenAI client for DeepSeek."""
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            api_key = self.key_manager.get_active_key()
        return AsyncOpenAI(api_key=api_key, base_url="https://api.deepseek.com")

    def _get_gemini_client(self):
        """Returns a modern Gemini client with explicit key."""
        # Force remove GOOGLE_API_KEY from env to prevent confusion if it's set to a Groq key
        if "GOOGLE_API_KEY" in os.environ and os.environ["GOOGLE_API_KEY"].startswith('gsk_'):
            del os.environ["GOOGLE_API_KEY"]
            
        # Re-read from env to be safe against accidental overwrites
        load_dotenv(override=True)
        api_key = os.getenv("GEMINI_API_KEY")
        
        if not api_key or not api_key.startswith('AIza'):
            logger.error("❌ GEMINI_API_KEY is missing or invalid in .env")
            raise ValueError("Invalid Gemini API Key")
            
        return google_genai.Client(api_key=api_key)

    def _track_spend(self, model_name: str, input_tokens: int, output_tokens: int):
        """Estimates, logs and persists spending based on model prices."""
        cost = 0.0
        if "flash" in model_name:
            # $0.075 / 1M input, $0.30 / 1M output
            cost = (input_tokens * 0.075 / 1_000_000) + (output_tokens * 0.30 / 1_000_000)
        elif "deepseek" in model_name:
            cost = (input_tokens * 0.27 / 1_000_000) + (output_tokens * 1.10 / 1_000_000)
        elif "llama-3.3-70b" in model_name:
            # Groq 70b approx: $0.59 / 1M input, $0.79 / 1M output
            cost = (input_tokens * 0.59 / 1_000_000) + (output_tokens * 0.79 / 1_000_000)
        
        if cost > 0:
            cost_try = cost * 33 # Approx 33 TL per USD
            
            # Persist spend data
            spend_file = os.path.join(os.getcwd(), 'data', 'ai_spend_history.json')
            history = load_json_safe(spend_file, default=[])
            entry = {
                "timestamp": datetime.now().isoformat(),
                "model": model_name,
                "input": input_tokens,
                "output": output_tokens,
                "cost_usd": cost,
                "cost_try": cost_try
            }
            history.append(entry)
            save_json_safe(spend_file, history)
            
            logger.info(f"💰 SPEND TRACKER [{model_name}]: ${cost:.6f} (~{cost_try:.4f} TL)")
            print(f"💰 [AI COST]: ${cost:.6f} (~{cost_try:.4f} TL) | Total Entries: {len(history)}")

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
        """Determines which model to use. Prioritize Gemini if requested."""
        return self.model_gemini

    def _tag_cities(self, text: str) -> str:
        """Finds all Turkish cities and tags them like [CITY] using safe regex replace."""
        if not text: return ""

        # --- BLACKLIST TRAP (Do not even try to validate these as locations) ---
        forbidden = ["HAFİF", "MADEN", "MERMER", "SOĞAN", "DEMİR", "KÖMÜR", "KARTON",
                     "SUNTA", "BRANDA", "NAKLİYE", "NAK", "LOJİSTİK",
                     "OLUR", "ÖLÜR", "GÜNÜ", "SAAT", "PARÇA", "PARCA"]
        
        # Standard Cities
        cities = ["ADANA", "ADIYAMAN", "AFYON", "AFYONKARAHİSAR", "AĞRI", "AKSARAY", "AMASYA", "ANKARA", "ANTALYA", "ARDAHAN", "ARTVİN", "AYDIN", "BALIKESİR", "BARTIN", "BATMAN", "BAYBURT", "BİLECİK", "BİNGÖL", "BİTLİS", "BOLU", "BURDUR", "BURSA", "ÇANAKKALE", "ÇANKIRI", "ÇORUM", "DENİZLİ", "DİYARBAKIR", "DÜZCE", "EDİRNE", "ELAZIĞ", "ERZİNCAN", "ERZURUM", "ESKİŞEHİR", "GAZİANTEP", "GİRESUN", "GÜMÜŞHANE", "HAKKARİ", "HATAY", "IĞDIR", "ISPARTA", "MERSİN", "İÇEL", "İSTANBUL", "İZMİR", "KAHRAMANMARAŞ", "KARABÜK", "KARAMAN", "KARS", "KASTAMONU", "KAYSERİ", "KIRIKKALE", "KIRKLARELİ", "KIRŞEHİR", "KİLİS", "KOCAELİ", "KONYA", "KÜTAHYA", "MALATYA", "MANİSA", "MARDİN", "MUĞLA", "MUŞ", "NEVŞEHİR", "NİĞDE", "ORDU", "OSMANİYE", "RİZE", "SAKARYA", "SAMSUN", "SİİRT", "SİNOP", "SİVAS", "ŞANLIURFA", "ŞIRNAK", "TEKİRDAĞ", "TOKAT", "TRABZON", "TUNCELİ", "UŞAK", "VAN", "YALOVA", "YOZGAT", "ZONGULDAK"]
        
        # Add Common Aliases & Major Logistics Hubs (Districts that act like Cities in logistics)
        aliases = ["ANTEP", "MARAŞ", "URFA", "GANTEP", "KMARAŞ", "ŞURFA"]
        hubs = ["KIZILTEPE", "GEBZE", "ÇORLU", "İNEGÖL", "İSKENDERUN", "ÇERKEZKÖY", "SİLİVRİ", "TUZLA", "DİLOVASI", "KEMALPAŞA", "MUSTAFAKEMALPAŞA"]
        
        all_locs = list(set(cities + aliases + hubs))
        all_locs.sort(key=len, reverse=True)
        
        tagged_text = text
        for loc in all_locs:
            # Safe regex for each loc: Case insensitive, Word boundary
            pattern = rf'\b{re.escape(loc)}\b'
            # Check if already tagged to avoid [[CITY]]
            if f"[{loc}]" in tagged_text.upper(): continue
            
            tagged_text = re.sub(pattern, lambda m: f"[{m.group(0).upper()}]", tagged_text, flags=re.IGNORECASE)
            
        return tagged_text

    def _clean_message(self, text: str) -> str:
        """Removes sticky emojis and normalizes text for better parsing."""
        if not text: return ""
        
        # --- STEP 0: Detect repeated emoji chains as shipment separators ---
        # e.g. "🚛🚛🚛🚛" = divider between two separate shipment ads
        text = re.sub(r'([\U0001F300-\U0001FFFF])\1{2,}', '\n---\n', text)
        
        # Normalize Bullet Points and List items to a standard format
        # Replace -, *, •, ●, ▪️, ▫️, 1., 2. at the start of lines with a space
        text = re.sub(r'^\s*[-*•●▪▫]\s*', ' ', text, flags=re.MULTILINE)
        text = re.sub(r'^\s*\d+[\.\)]\s*', ' ', text, flags=re.MULTILINE)

        # Common emojis that stick to words
        stickies = ['📍', '➡️', '🚚', '📦', '🧅', '📞', '👉', '👉🏻', '👉🏼', '✅', '🚛']
        for s in stickies:
            text = text.replace(s, f" {s} ")
        
        # Replace arrow-like symbols with standard arrows
        text = text.replace('👉', ' -> ').replace('➡️', ' -> ').replace('👉🏻', ' -> ')
        
        # City Abbreviation Normalization (with dots)
        text = text.replace('İST.', ' İSTANBUL ').replace('ANK.', ' ANKARA ').replace('İZM.', ' İZMİR ')
        text = text.replace('KOC.', ' KOCAELİ ').replace('BUR.', ' BURSA ')
        
        # Separate locations joined by + or / (e.g. URFA+ADANA -> URFA + ADANA)
        text = re.sub(r'([a-zA-ZİıĞğÜüŞşÖöÇç])\+([a-zA-ZİıĞğÜüŞşÖöÇç])', r'\1 + \2', text)
        text = re.sub(r'([a-zA-ZİıĞğÜüŞşÖöÇç])\/([a-zA-ZİıĞğÜüŞşÖöÇç])', r'\1 / \2', text)

        # Collapse multiple spaces but preserve line breaks
        lines = text.split('\n')
        lines = [' '.join(line.split()) for line in lines]
        text = '\n'.join(lines)
        
        # --- AUTO TAG CITIES ---
        return self._tag_cities(text)

    async def _extract_locations_stage1_async(self, message: str) -> str:
        """Stage 1: Fast extraction of just origins and destinations (Async)."""
        clean_msg = self._clean_message(message)
        
        # --- REGEX DISCOVERY ---
        # Find all Turkish cities tagged in the message to give AI a hint
        # The message is already tagged by parse_async -> _clean_message
        found_tags = re.findall(r'\[(.*?)\]', clean_msg)
        hint = f"\nIDENTIFIED CITIES (TAGGED AS [CITY]): {', '.join(found_tags)}" if found_tags else ""

        system_prompt = "You are a logistics location extractor. If you see a multi-origin pattern like 'A+B+C -> D', you MUST output them as separate lines:\nA -> D\nB -> D\nC -> D\nNEVER join them with '+'. Output ONLY the routes in 'ORIGIN -> DESTINATION' format."
        user_prompt = f"Extract routes from this logistics message. {hint}\n\nMESSAGE:\n{clean_msg}"
        model_to_use = self.model_gemini
        
        with self.semaphore:
            for attempt in range(3):
                try:
                    if "gemini" in model_to_use:
                        client = self._get_gemini_client()
                        response = await asyncio.to_thread(
                            client.models.generate_content,
                            model=model_to_use,
                            contents=f"{system_prompt}\n\n{user_prompt}"
                        )
                        text = response.text
                        self._track_spend(model_to_use, response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count)
                        return text.strip()
                    else:
                        # Fallback for Stage 1 if needed
                        client = self._get_async_client()
                        response = await client.chat.completions.create(
                            model=self.model_fast,
                            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                            temperature=0.0
                        )
                        text = response.choices[0].message.content
                        self._track_spend(self.model_fast, response.usage.prompt_tokens, response.usage.completion_tokens)
                        return text.strip()
                except RuntimeError as e:
                    if "interpreter shutdown" in str(e):
                        return ""
                    raise
                except Exception as e:
                    error_str = str(e)
                    if "429" in error_str and "gemini" in model_to_use:
                        logger.warning(f"Stage 1 Gemini Rate Limit. Rotating key...")
                        if await self.key_manager.switch_to_next_async(key_type='google', reason="Stage 1 Limit"):
                            continue
                    
                    print(f"STAGE 1 ERROR: {e}")
                    logger.warning(f"Stage 1 Async failed: {str(e)[:100]}")
                    return ""
        return ""

    async def parse_async(self, message: str) -> list:
        """Asynchronously parse logistics message with full logic recovery."""
        # 0. Clean Message (Emoji separation, symbol normalization)
        message = self._clean_message(message)
        
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
LOGISTICS ABBREVIATIONS & RULES:
- "İ." or "İZM" followed by "KEMALPAŞA" ALWAYS means "İZMİR / KEMALPAŞA".
- "K.PAŞA" or "K. PASA" usually means "KEMALPAŞA".
- EXTREME PRIORITY: If "BURSA" is mentioned anywhere in the message, "KEMALPAŞA" or "K.PAŞA" MUST be extracted as "BURSA / MUSTAFAKEMALPAŞA". DO NOT extract it as İzmir if Bursa is present.
- "İST" = İSTANBUL, "İZM" = İZMİR, "ANK" = ANKARA, "KOC" = KOCAELİ.
- "M." followed by "YATAĞAN" means "MUĞLA / YATAĞAN".
- "DİLOVASI" is a district in KOCAELİ.
- "GEBZE" is a district in KOCAELİ.
- "X'TEN Y'YE" or "X - Y" patterns: X is ORIGIN, Y is DESTINATION.

VALID TURKISH CITIES: ADANA, ADIYAMAN, AFYONKARAHİSAR, AĞRI, AKSARAY, AMASYA, ANKARA, ANTALYA, ARDAHAN, ARTVİN, AYDIN, BALIKESİR, BARTIN, BATMAN, BAYBURT, BİLECİK, BİNGÖL, BİTLİS, BOLU, BURDUR, BURSA, ÇANAKKALE, ÇANKIRI, ÇORUM, DENİZLİ, DİYARBAKIR, DÜZCE, EDİRNE, ELAZIĞ, ERZİNCAN, ERZURUM, ESKİŞEHİR, GAZİANTEP, GİRESUN, GÜMÜŞHANE, HAKKARİ, HATAY, IĞDIR, ISPARTA, MERSİN, İSTANBUL, İZMİR, KAHRAMANMARAŞ, KARABÜK, KARAMAN, KARS, KASTAMONU, KAYSERİ, KIRIKKALE, KIRKLARELİ, KIRŞEHİR, KİLİS, KOCAELİ, KONYA, KÜTAHYA, MALATYA, MANİSA, MARDİN, MUĞLA, MUŞ, NEVŞEHİR, NİĞDE, ORDU, OSMANİYE, RİZE, SAKARYA, SAMSUN, SİİRT, SİNOP, SİVAS, ŞANLIURFA, ŞIRNAK, TEKİRDAĞ, TOKAT, TRABZON, TUNCELİ, UŞAK, VAN, YALOVA, YOZGAT, ZONGULDAK."""

        user_prompt = f"""Extract ALL routes from this message. 
STRICT RULE: Only extract routes explicitly stated. Do NOT invent locations.

{loc_guideline}

EXAMPLE OF VERTICAL LIST PARSING:
Message:
ADANA CUMARTESİ YÜKLEME
İSTANBUL AVR. 2 NOKTA
ANKARA TEK NOKTA
0532...
Expected Logic:
- Global Origin: ADANA
- Route 1: ADANA -> İSTANBUL (AVR)
- Route 2: ADANA -> ANKARA (MERKEZ)

EXTRACTION & LOGIC RULES:
1. HARD HIERARCHY: City > District > Neighborhood. ALWAYS identify the CITY (İL) first. 
2. NO HALLUCINATION: If a location is not in the message, DO NOT add it. Do NOT invent routes.
3. SUFFIXES: -den/-dan indicates ORIGIN, -e/-a indicates DESTINATION.
4. ORDER: In "A B" patterns, A is ALWAYS the ORIGIN even if B is a City and A is a District (e.g. "KIZILTEPE ANTEP" means KIZILTEPE -> ANTEP).
5. GLOBAL ORIGIN (HEADER-BASED): If a message starts with a location (e.g., "NİĞDE CUMARTESİ YÜKLEME") and then lists multiple locations line-by-line, that first location is the ORIGIN for ALL subsequent locations.
6. VERTICAL LISTS: In a vertical list where each line contains a location (e.g., "ALANYA TEK NOKTA", "ADANA 3 NOKTA"), these locations are ALWAYS the DESTINATIONS (nereye). The origin (nereden) is taken from the header.
7. MULTI-DESTINATION (X NOKTA): Expressions like "ADANA 3 NOKTA" or "İZMİR 2 NOKTA" indicate that the location mentioned (ADANA, İZMİR) is the DESTINATION. The number (3, 2) is the count of drops at that destination.
8. PLUS SIGN IN LIST: If a line in a vertical list is "DÜZCE + İSTANBUL", it means İki AYRI varış noktası (Separate destinations) from the same origin. Create two separate route objects.
9. VERTICAL LIST RESET: If a new company name, phone number, or keywords like "YÜK", "YÜKLEME", "YENİ YÜK" appear at the top of a new block, the previous global origin is RESET.
10. NO CHAINING: Treat each target as a separate route from the main origin. NEVER create routes between two destination points in a list.
11. MULTI-ROUTE SYMBOLS: 
   - "X'den Y ve Z'ye" = (X->Y) and (X->Z). 
   - "X + Y + Z -> A" or "X/Y/Z -> A" = (X->A), (Y->A), (Z->A). EACH location before the arrow is a separate ORIGIN.
12. STOP COUNTS: Ignore "TEK NOKTA", "2 NOKTA", "3 YER", "DÖNÜŞLÜ". Do NOT extract numbers as districts.
13. COMPANY NAME: Extract company/person into "isim". It is usually at the bottom.
14. VEHICLE & LOAD: "13.60" and "860" are vehicle types. "HAFİF" and "OLUR" are NOT locations.
15. NO GUESSING (STRICT): If a district is not explicitly mentioned, use "MERKEZ". NEVER guess districts like "MALTEPE" or "BORNOVA".
16. ISTANBUL DISTRICTS: If you see "AVR", set nereye_ilce="AVR". If you see "AND", set nereye_ilce="AND".
17. GLOBAL DESTINATION: If a message says "X VARIŞLI" at the top and then lists cities, those cities are the ORIGINS, and X is the DESTINATION for all of them.
18. MANDATORY: Every JSON route MUST have "nereden_il", "nereden_ilce", "nereye_il", "nereye_ilce", "type", "isim".

{loc_context}
{rules_context}

MESSAGE TO PARSE:
{message.strip()}

Return ONLY a JSON object: 
{{"akil_yurutme": "Mesaj dikey liste yapısındadır. Baştaki konum [CITY] çıkış noktasıdır. Diğerleri varış noktasıdır.", "routes": [{{ "nereden_il": "CITY", "nereden_ilce": "DISTRICT", "nereye_il": "CITY", "nereye_ilce": "DISTRICT", "type": "VEHICLE", "isim": "COMPANY" }}]}}"""

        # 413 Payload Too Large protection
        if len(message) > 8000:
            message = message[:8000] + "... [TRUNCATED]"

        models_to_try = [target_model, self.model_robust, self.model_fast]
        models_to_try = list(dict.fromkeys(models_to_try))

        with self.semaphore:
            for model_name in models_to_try:
                for attempt in range(3):
                    try:
                        if "gemini" in model_name:
                            client = self._get_gemini_client()
                            response = await asyncio.to_thread(
                                client.models.generate_content,
                                model=model_name,
                                contents=f"{system_prompt}\n\n{user_prompt}"
                            )
                            text = response.text
                            self._track_spend(model_name, response.usage_metadata.prompt_token_count, response.usage_metadata.candidates_token_count)
                        elif "deepseek" in model_name:
                            client = self._get_deepseek_client()
                            response = await client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                                temperature=0.0,
                                response_format={"type": "json_object"}
                            )
                            text = response.choices[0].message.content
                            self._track_spend(model_name, response.usage.prompt_tokens, response.usage.completion_tokens)
                        else:
                            client = self._get_async_client()
                            response = await client.chat.completions.create(
                                model=model_name,
                                messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                                temperature=0.0,
                                response_format={"type": "json_object"}
                            )
                            text = response.choices[0].message.content
                            self._track_spend(model_name, response.usage.prompt_tokens, response.usage.completion_tokens)
                        
                        text = text.strip()
                        print(f"\n[DEBUG] AI RESPONSE:\n{text}\n") 
                        return await self._process_raw_json_async(text, message)
                    except RuntimeError as e:
                        if "interpreter shutdown" in str(e):
                            return []
                        raise
                    except Exception as e:
                        error_str = str(e)
                        print(f"⚠️ STAGE 2 ERROR [{model_name}]: {error_str[:150]}")
                        
                        if "429" in error_str:
                            # --- SMART WAIT LOGIC ---
                            wait_sec = 5 # Default
                            # Try to extract seconds from message: "Try again in 12.5s"
                            match = re.search(r"try again in ([\d\.]+)s", error_str.lower())
                            if match:
                                wait_sec = float(match.group(1)) + 0.5
                                logger.info(f"⏳ Groq requested explicit wait: {wait_sec}s")
                            
                            if "gemini" in model_name:
                                if await self.key_manager.switch_to_next_async(key_type='google', reason=f"Rate Limit {model_name}"):
                                    logger.warning(f"🔄 Gemini Limit. Switching key and waiting {wait_sec}s...")
                                    await asyncio.sleep(wait_sec)
                                    continue
                                else:
                                    break
                            
                            # Rotate Groq keys
                            if await self.key_manager.switch_to_next_async(key_type='groq', reason=f"Rate Limit {model_name}"):
                                logger.warning(f"🔄 Groq Limit on {model_name}. Switching key and waiting {wait_sec}s...")
                                await asyncio.sleep(wait_sec)
                                continue
                            else:
                                # All exhausted, wait longer before failing
                                logger.error(f"🚨 ALL KEYS EXHAUSTED! Cooling down for {wait_sec*2}s...")
                                await asyncio.sleep(wait_sec * 2)
                                break
                        elif "401" in error_str or "400" in error_str:
                            logger.error(f"AUTH/CONFIG ERROR on {model_name}: {error_str}")
                            if not "gemini" in model_name:
                                await self.key_manager.switch_to_next_async(reason=f"Error {model_name}")
                            break
                        
                        await asyncio.sleep(1)
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

    def _extract_price_regex(self, text: str) -> str:
        """
        Extracts price from a single line or short text using regex rules.
        USER REQUEST: Always return 'SORUNUZ'.
        """
        return "SORUNUZ"
        
        # 1. Clean up and normalize
        clean_text = text.upper().replace('İ', 'I').replace('₺', ' TL ')
        
        # 2. Pattern to find numbers (including decimals/thousands)
        # Simplified pattern: match any number sequence with potential separators
        pattern = r'(?<!\d)(\d{1,3}(?:[\.,]\d{3})*(?:[\.,]\d{1,2})?|\d+)(?!\d)'
        
        matches = list(re.finditer(pattern, clean_text))
        candidates = []
        for m in matches:
            val_str = m.group(1)
            # Remove dots/commas to check digits only
            digits = re.sub(r'\D', '', val_str)
            
            # Normalize for comparison
            val_norm = val_str.replace(',', '.')
            
            # 3. STRICT VALIDATION RULES:
            # - Has decimal/thousands separator (e.g. 15.000)
            # - OR Has price keywords nearby (e.g. 450 TL, 450+KDV)
            has_separator = '.' in val_str or ',' in val_str
            
            # Check surrounding context (15 chars before/after)
            surrounding = clean_text[max(0, m.start()-15):min(len(clean_text), m.end()+15)]
            # Added '+' and 'KDV' variations
            price_keywords = ['TL', 'KDV', 'FIYAT', 'HESAP', 'DAHIL', 'GIRIS', 'CORDER', '+']
            has_keyword = any(kw in surrounding for kw in price_keywords)

            # 4. CRITICAL: 13.60 and 860 are usually vehicle types.
            # Exclude them ONLY IF they don't have price keywords nearby.
            if val_norm in ['13.60', '1360', '860']:
                if not has_keyword:
                    continue
            
            # 5. CRITICAL: Exclude Phone Numbers
            if len(digits) >= 10 and (digits.startswith('05') or digits.startswith('5')):
                continue
            if (len(digits) in [3, 4]) and (digits.startswith('05') or digits.startswith('5')):
                after = clean_text[m.end():m.end()+10]
                if re.search(r'\d', after):
                    continue
            
            if not (has_separator or has_keyword):
                continue

            # Calculate context score
            score = 0
            if has_keyword: score += 10
            if has_separator: score += 5
                
            candidates.append((val_str, score, m.start()))

        if not candidates:
            return "SORUNUZ"
            
        # Sort by score descending, then by position (prefer later in line)
        candidates.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return candidates[0][0]

    async def _process_raw_json_async(self, text, message):
        """Processes raw JSON into validated routes (Async version)."""
        try:
            data = json.loads(text)
        except:
            json_match = re.search(r'\{.*\}|\[.*\]', text, re.DOTALL)
            data = json.loads(json_match.group()) if json_match else {"routes": []}
        
        raw_routes = data.get('routes', [])
        final_routes = []
        
        # Pre-process message for context
        msg_lines = message.split('\n')
        msg_up = message.upper().replace('İ', 'İ').replace('I', 'I')
        phone_match = re.search(r"(0\s*5\d{2}[\s\.\-\(\)]*\d{3}[\s\.\-\(\)]*\d{2}[\s\.\-\(\)]*\d{2})", message)
        default_phone = re.sub(r'\D', '', phone_match.group(1)) if phone_match else ""
        global_type_match = self.vehicle_matcher.find_match(message, per_route=False)
        
        # --- GLOBAL PRICE DETECTION ---
        global_price = "SORUNUZ"
        for line in msg_lines:
            line_up = line.upper()
            # Exclude lines that look like routes (containing arrows or "to")
            is_route_line = any(c in line_up for c in ['➡️', '->', '➝', '➞', '➞', '➞', '➞', 'DEN', 'DAN'])
            if not is_route_line and any(kw in line_up for kw in ['TL', 'KDV', 'FIYAT', 'HESAP', 'DAHIL']):
                p = self._extract_price_regex(line)
                if p != "SORUNUZ":
                    global_price = p
                    break

        for r in raw_routes:
            # 1. Contextual Corrections
            n_il   = r.get('nereden_il', '') or ''
            n_dist = r.get('nereden_ilce', '') or ''
            ny_il  = r.get('nereye_il', '') or ''
            ny_dist = r.get('nereye_ilce', '') or ''

            # 2. Strict Validation via Registry
            n_il, n_dist = self.city_validator.validate(n_il, n_dist)
            ny_il, ny_dist = self.city_validator.validate(ny_il, ny_dist)

            # 3. Neighborhood fallback if still missing district
            if not n_dist and r.get('nereden_ilce'):
                n_il, n_dist = await self._resolve_neighborhood_async(r.get('nereden_ilce'), n_il)
                n_il, n_dist = self.city_validator.validate(n_il, n_dist)

            if not ny_dist and r.get('nereye_ilce'):
                ny_il, ny_dist = await self._resolve_neighborhood_async(r.get('nereye_ilce'), ny_il)
                ny_il, ny_dist = self.city_validator.validate(ny_il, ny_dist)

            # 4. Vehicle & Load Type Matching (Line-by-Line Context)
            # Find the specific line for this route to get accurate local context (metre, etc.)
            search_terms = [r.get('nereye_il', ''), r.get('nereye_ilce', ''), ny_il, ny_dist]
            if ny_dist == 'KAHRAMANKAZAN': search_terms.append('KAZAN')
            if ny_dist == 'MUSTAFAKEMALPAŞA': search_terms.append('KEMALPAŞA')
            
            found_line = ""
            search_terms = [s for s in search_terms if s and len(s) > 2]
            
            # Use a normalized search to find the correct line regardless of Turkish chars
            def quick_norm(t):
                return t.upper().replace('İ', 'I').replace('ı', 'I').replace('Ğ', 'G').replace('Ü', 'U').replace('Ş', 'S').replace('Ö', 'O').replace('Ç', 'C')

            for line in msg_lines:
                norm_line = quick_norm(line)
                if any(quick_norm(term) in norm_line for term in search_terms):
                    found_line = line
                    break
            
            # Match using the specific line context + AI type suggestion
            route_context = f"{found_line} {r.get('type', '')}" if found_line else f"{n_il} {ny_il} {r.get('type', '')}"
            type_match = self.vehicle_matcher.find_match(route_context, per_route=True)
            
            if not type_match and global_type_match:
                type_match = global_type_match

            if type_match:
                arac_tipi = [type_match.get('ARAÇ TİPİ', '1360')]
                kasa_tipi = [k.strip() for k in type_match.get('KASA TİPİ', 'AÇIK KAPALI').split('+')]
                yuk_tipi = [type_match.get('YÜKÜN TİPİ', 'KOMPLE')]
            else:
                arac_tipi = ['1360']
                kasa_tipi = ['AÇIK', 'KAPALI']
                yuk_tipi = ['KOMPLE']

            # --- PRICE EXTRACTION (DISABLED BY USER REQUEST) ---
            fiyat = "SORUNUZ"

            route = {
                "isim": r.get('isim', 'Bilinmiyor'),
                "nereden_il": n_il,
                "nereden_ilce": n_dist,
                "nereye_il": ny_il,
                "nereye_ilce": ny_dist,
                "arac_tipi": arac_tipi,
                "kasa_tipi": kasa_tipi,
                "yuk_tipi": yuk_tipi,
                "fiyat": fiyat,
                "telefon": r.get('telefon', default_phone) or default_phone,
                "aciklama": message[:100],
                "createdAt": datetime.now().isoformat(),
                "body": message
            }
            final_routes.append(route)
            
        return final_routes

    async def _resolve_neighborhood_async(self, term: str, context_city: str = "") -> tuple:
        """Attempts to resolve neighborhood using AI (Async version)."""
        cache_key = f"{term.upper().strip()}|{context_city.upper().strip()}"
        if cache_key in self.neighborhood_cache:
            res = self.neighborhood_cache[cache_key]
            return tuple(res) if res else ("", "")

        with self.semaphore:
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
