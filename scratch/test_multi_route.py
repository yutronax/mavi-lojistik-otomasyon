import sys
import os
import asyncio

# Add project root to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

async def test_complex_message():
    parser = TextGenParser()
    
    msg = """✅BİLECİK VEZİRHAN YÜKLEME 
🚀AÇIK ARAÇLAR 
📍 ANKARA SİTELER 3 ARABA 600+
📍 ANKARA PURSAKLAR 1 ARABA 625+
📍 ANKARA ÇUBUK  6 TIR 650 +
📍 ANKARA AKYURT 3 TIR : 625+
📍ANKARA OVACIK 2 TIR 600 +
☎️0552 092 88 560"""

    print("="*60)
    print("COMPLEX MULTI-ROUTE TEST")
    print("="*60)
    
    result = parser.parse(msg)
    
    import json
    print("\n--- PARSER RESULT ---")
    print(json.dumps(result, indent=3, ensure_ascii=False))
    
    # result is likely a list of routes now based on previous changes
    routes = result if isinstance(result, list) else result.get('routes', [])
    print(f"\nFinal Result: {len(routes)} routes found.")
    for i, r in enumerate(routes, 1):
        print(f"  Route {i}: {r.get('nereden_il')} {r.get('nereden_ilce')} -> {r.get('nereye_il')} {r.get('nereye_ilce')} ({r.get('fiyat')})")

if __name__ == "__main__":
    asyncio.run(test_complex_message())
