import sys
import os
import asyncio
import json

# Add project root to path
PROJECT_ROOT = r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik'
sys.path.insert(0, PROJECT_ROOT)

from production_parser import ProductionParser

async def test_parse():
    parser = ProductionParser()
    message = """📍Erzin ➝ Çumra 860+Kdv
📍Erzin ➝ Cihanbeyli 900+kdv
▫️ 13.60 Açık Tır-Kapalı sınırsız araç
▫️ Çuvallı Gübre
▫️7-24 Yükleme Mevcut 
📞05419677835
✨CEYLAN LOJİSTİK NAKLİYE ✨"""

    print("--- PARSING MESSAGE ---")
    results = parser.parse_message(message)
    
    print(f"\nFound {len(results)} routes:")
    for i, r in enumerate(results, 1):
        print(f"\n[Route {i}]")
        print(f"  Origin: {r.get('nereden_il')} / {r.get('nereden_ilce')}")
        print(f"  Dest:   {r.get('nereye_il')} / {r.get('nereye_ilce')}")
        print(f"  Price:  {r.get('fiyat')}")
        print(f"  Tel:    {r.get('telefon')}")
        print(f"  Kasa:   {r.get('kasa_tipi')}")

if __name__ == "__main__":
    asyncio.run(test_parse())
