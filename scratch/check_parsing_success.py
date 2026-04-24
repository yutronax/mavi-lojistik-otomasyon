import sys
import os
import asyncio
import json
from datetime import datetime

# Path setup
sys.path.insert(0, os.getcwd())
from text_gen_parser import TextGenParser

async def run_success_test():
    parser = TextGenParser()
    
    test_cases = [
        {
            "name": "Basit Rota",
            "message": "ADANA - İSTANBUL TIR KOMPLE",
            "expected": "ADANA -> İSTANBUL (1360)"
        },
        {
            "name": "İlçe ve Mahalle",
            "message": "İSTANBUL TUZLA YÜKLER ANKARA SİNCAN BOŞALTIR",
            "expected": "İSTANBUL/TUZLA -> ANKARA/SİNCAN"
        },
        {
            "name": "Çoklu Durak (Multi-stop)",
            "message": "KOCAELİ GEBZE'DEN ÇIKAR - BURSA VE BALIKESİR'E",
            "expected": "GEBZE -> BURSA, GEBZE -> BALIKESİR"
        },
        {
            "name": "Kemalpaşa Tuzağı (Bursa)",
            "message": "BURSA KEMALPAŞA YÜKLER İZMİR BOŞALTIR",
            "expected": "BURSA/MUSTAFAKEMALPAŞA -> İZMİR"
        },
        {
            "name": "Kemalpaşa Tuzağı (İzmir)",
            "message": "İZMİR KEMALPAŞA YÜKLER ANKARA BOŞALTIR",
            "expected": "İZMİR/KEMALPAŞA -> ANKARA"
        },
        {
            "name": "Araç Tipi (40 Ayak)",
            "message": "DÜZCE - SAKARYA 40 AYAK LAZIM",
            "expected": "DÜZCE -> SAKARYA (KIRKAYAK)"
        },
        {
            "name": "Fiil Bağlamı (Loading/Unloading)",
            "message": "EREĞLİ YÜKLER ADAPAZARI BOŞALTIR",
            "expected": "ZONGULDAK/EREĞLİ -> SAKARYA/ADAPAZARI"
        },
        {
            "name": "Parça Yük",
            "message": "İSTANBUL AVRUPA YAKASI - ANKARA 3 PALET 5 TON",
            "expected": "İSTANBUL -> ANKARA (PARÇA)"
        }
    ]
    
    print(f"--- AYRIŞTIRMA BAŞARI TESTİ ---")
    print(f"Tarih: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*60}")
    
    total = len(test_cases)
    passed = 0
    
    for i, case in enumerate(test_cases, 1):
        print(f"\nTEST {i}: {case['name']}")
        print(f"Mesaj: {case['message']}")
        
        try:
            # We need to access the raw data to see akil_yurutme
            # But parse_async returns final_routes. 
            # I'll modify check_parsing_success to use a modified version or just trust the result.
            # Actually, I'll just check the result and if it's wrong, I'll investigate.
            results = await parser.parse_async(case['message'])
            print(f"Sonuç: {len(results)} rota bulundu.")
            
            for j, r in enumerate(results, 1):
                print(f"  [{j}] {r['nereden_il']}/{r['nereden_ilce']} -> {r['nereye_il']}/{r['nereye_ilce']}")
                print(f"      Araç: {r['arac_tipi']}, Yük: {r['yuk_tipi']}")
            
            if len(results) > 0:
                passed += 1
                print("✅ Başarılı (Veri çıkarıldı)")
            else:
                print("❌ Başarısız (Veri çıkarılamadı)")
                
        except Exception as e:
            print(f"💥 HATA: {e}")
            
    print(f"\n{'='*60}")
    print(f"ÖZET: {passed}/{total} test veri çıkışı sağladı.")
    print(f"{'='*60}")

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(run_success_test())
