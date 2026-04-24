import sys
import os
import asyncio
import nest_asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

import logging
logging.basicConfig(level=logging.INFO)
nest_asyncio.apply()

async def test_gemini_spend():
    parser = TextGenParser()
    # Force Gemini
    parser.model_gemini = "gemini-2.0-flash"
    
    msg = "İzmir Kemalpaşa yükler, Ankara Sincan boşaltır. 25 ton komple araç lazım."
    
    print(f"\n--- GEMINI SPEND TEST ---")
    print(f"Message: {msg}")
    
    results = await parser.parse_async(msg)
    
    print(f"\n--- RESULTS ---")
    for r in results:
        print(f"{r.get('nereden_il')}/{r.get('nereden_ilce')} -> {r.get('nereye_il')}/{r.get('nereye_ilce')}")

if __name__ == "__main__":
    asyncio.run(test_gemini_spend())
