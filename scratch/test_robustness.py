import sys
import os
import asyncio
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

async def run_test(parser, name, message):
    print(f"\n{'='*20} TEST: {name} {'='*20}")
    print(f"Message:\n{message}\n")
    
    routes = parser.parse(message)
    print(f"Found {len(routes)} routes:")
    for i, r in enumerate(routes, 1):
        print(f"  [{i}] {r.get('nereden_il')} {r.get('nereden_ilce')} -> {r.get('nereye_il')} {r.get('nereye_ilce')} | Arac: {r.get('arac_tipi')} | Kasa: {r.get('kasa_tipi')} | Fiyat: {r.get('fiyat')}")
    print("-" * 60)

async def main():
    parser = TextGenParser()
    
    scenarios = [
        {
            "name": "VARYASYON 1: Farklı Anahtar Kelimeler (ÇIKIŞLI / VARİŞ)",
            "msg": "MARAŞ ÇIKIŞLI KOMPLE TENTELİ\n- İSTANBUL TUZLA\n- KOCAELİ GEBZE\n- BURSA İNEGÖL"
        },
        {
            "name": "VARYASYON 2: Çıkış Noktası Değişen Liste",
            "msg": "YÜKLEME TOPKAPI -> SİTELER ANKARA\nYÜKLEME HADIMKÖY -> BURSA"
        },
        {
            "name": "VARYASYON 3: Sadece Mahalle ve İlçe (Karışık)",
            "msg": "SİTELER'DEN - ÇUBUK VE PURSAKLAR'A 3 ARABA 600+"
        },
        {
            "name": "VARYASYON 4: Çoklu Araç ve Parça Yük",
            "msg": "İSTANBUL VEZİRHAN YÜKLER - ANKARA SİTELER TIRA PARÇA + 10 TEKER KOMPLE"
        }
    ]
    
    for sc in scenarios:
        await run_test(parser, sc['name'], sc['msg'])

if __name__ == "__main__":
    asyncio.run(main())
