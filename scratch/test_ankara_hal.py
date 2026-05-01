import asyncio
import os
import sys
import json

# Add current directory to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

async def test_ankara_error():
    parser = TextGenParser()
    msg = """
YARIN YÜKLER
ANKARA GÖL • İST.TUZLA TIR ÖDEME PEŞİN
ANKARA GÖL • İST.ARNAVUTKÖY TIR ÖDEME PEŞİN
    """
    print(f"PARSING MESSAGE:\n{msg}")
    results = await parser.parse_async(msg)
    
    print("\nPARSED JSON:")
    print(json.dumps(results, indent=4, ensure_ascii=False))
    
    print("\nSUMMARY:")
    for i, r in enumerate(results):
        print(f"{i+1}. {r.get('nereden_il')}/{r.get('nereden_ilce')} -> {r.get('nereye_il')}/{r.get('nereye_ilce')}")

if __name__ == "__main__":
    asyncio.run(test_ankara_error())
