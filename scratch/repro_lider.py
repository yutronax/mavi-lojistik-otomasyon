import asyncio
import json
import os
import sys

# Add current directory to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

async def test_lider():
    parser = TextGenParser()
    message = """🚚LİDER NAKLİYAT 🚚

81 İL VE İLÇEYE KAPALI TENTEN 
TERMOKİN YÜKLEMEM VAR.  

05521025624☎️

KIZILTEPE ANTEP MERKEZ 
KIZILTEPE MARAŞ MERKEZ 
KIZILTEPE HATAY MERKEZ
KIZILTEPE MERSİN MERKEZ 
KIZILTEPE ADANA MERKEZ 
KIZILTEPE İSKENDERUN MERKEZ 
KIZILTEPE İSKENDERUN ARSUZ 
KIZILTEPE OSMANİYE KADİRLİ 

05521025624☎️

🚚LİDER NAKLİYAT🚚"""

    print("Parsing message...")
    results = await parser.parse_async(message)
    
    print("\nPARSED RESULTS:")
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['nereden_il']}/{r['nereden_ilce']} -> {r['nereye_il']}/{r['nereye_ilce']}")
    
    # Save to file for inspection
    with open('scratch/lider_debug_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    asyncio.run(test_lider())
