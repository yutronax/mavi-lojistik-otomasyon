import sys
import os
import json
sys.path.insert(0, os.getcwd())
from text_gen_parser_optimized import TextGenParser

def test_case(msg, name):
    print("\n" + "=" * 80)
    print(f"CASE: {name}")
    print("=" * 80)
    print(f"MESSAGE:\n{msg}\n")
    
    parser = TextGenParser()
    results = parser.parse(msg)
    
    print("-" * 80)
    print(f"✓ Parsed {len(results)} routes")
    for i, r in enumerate(results, 1):
        print(f"[Route {i}]")
        print(f"  {r['nereden_il']}/{r['nereden_ilce']} → {r['nereye_il']}/{r['nereye_ilce']}")
        print(f"  Araç: {' + '.join(r['arac_tipi'])}")
        print(f"  Kasa: {' + '.join(r['kasa_tipi'])}")
        print(f"  Yük : {' + '.join(r['yuk_tipi'])}")
    print("-" * 80)
    return results

if __name__ == "__main__":
    # Senaryo 1: Başlık Etkisi (Global Origin) + Dinamik Kurallar (Mısır)
    msg1 = """KIZILTEPEDEN✅✅
MALATYAYA MISIR 🌽 
KISA DORSA  

ADANA KARATAŞ MISIR 🌽 
KISA DORSA ✅

CEYHAN MISIR"""
    
    # Senaryo 2: Yük İlanı (Origin in line 1) + Karışık Tipler
    msg2 = """*Bursa Mustafakemalpaşa yükler*
Düzce mısır 20 ton damperli
İstanbul tır brandalı parça gıda
Antalya 10 teker parsiyel"""

    # Senaryo 3: Tek Satır Çoklu Destinasyon + Telefon + Fiyat
    msg3 = "ANKARA - İZMİR + MUĞLA + MANİSA 13.60 KAPALI TIR SORUNUZ 0532 999 88 77"

    test_case(msg1, "HEADER EFFECT + DYNAMIC RULES")
    test_case(msg2, "LINE-BY-LINE MIXED TYPES")
    test_case(msg3, "SINGLE LINE MULTI-DESTINATION")
