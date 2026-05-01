import asyncio
import json
import sys
import os

# Project root for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from text_gen_parser import TextGenParser

async def test_vertical_parsing():
    parser = TextGenParser()
    
    test_cases = [
        {
            "name": "Standard Vertical (Global Origin)",
            "message": """İSTANBUL YÜKLEME
ADANA 3 NOKTA
MERSİN TEK NOKTA
ANTEP 2 YER
0532 000 00 00"""
        },
        {
            "name": "Global Destination",
            "message": """ANTALYA VARIŞLI YÜKLER
İSTANBUL DEN
KOCAELİ DEN
SAKARYA DAN
XYZ LOJİSTİK"""
        },
        {
            "name": "Mixed Bullet Points",
            "message": """ADANA ÇIKIŞ
* İSTANBUL (AVR)
- ANKARA
• İZMİR
0555 555 55 55"""
        },
        {
            "name": "Plus Sign in List",
            "message": """BURSA ÇIKIŞLI
DÜZCE + İSTANBUL
BOLU
ABC NAKLİYE"""
        },
        {
            "name": "Multi-Origin to Single Destination",
            "message": """ADANA + MERSİN + ANTEP -> İSTANBUL
13.60 TIR
0544 444 44 44"""
        }
    ]
    
    print("=" * 80)
    print("DIKEY MESAJ AYRIŞTIRMA TESTI")
    print("=" * 80)
    
    for case in test_cases:
        print(f"\n[TEST] {case['name']}")
        print(f"Mesaj:\n{case['message']}")
        print("-" * 40)
        
        try:
            results = await parser.parse_async(case['message'])
            print(f"Sonuç: {len(results)} rota bulundu.")
            for i, r in enumerate(results, 1):
                print(f"  {i}. {r['nereden_il']}/{r['nereden_ilce']} -> {r['nereye_il']}/{r['nereye_ilce']}")
        except Exception as e:
            print(f"HATA: {e}")
        
        await asyncio.sleep(2) # Rate limit protection
        print("-" * 80)

if __name__ == "__main__":
    asyncio.run(test_vertical_parsing())
