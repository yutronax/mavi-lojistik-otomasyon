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
        print(f"  Fiyat: {r['fiyat']}")
    print("-" * 80)
    return results

if __name__ == "__main__":
    # Senaryo 1: 7.20 ve Paletli yüklerin karışık olduğu bir liste
    msg1 = """*GÜNCEL YÜKLER* 🚢 🚢 🚢 🚢 🚢 

İSTANBUL İKİTELLİ - ANKARA OSTİM
7.20 TIR BRANDALI GIDA

BURSA - İZMİR 
2 PALETLİ PARÇA 

KOCAELİ GEBZE - MANİSA 
3 PALETLİ GIDA 10 TEKER

MERSİN - GAZİANTEP
13.60 FRİGO 22 TON"""

    # Senaryo 2: "7 2" yazım formatı ve büyük mesaj
    msg2 = """DÜZCE AKÇAKOCADAN✅✅
İSTANBUL TUZLA 7 20 BRANDALI
İZMİRE 7 20 BRANDALI 
ANKARA 7 20 BRANDALI
KAYSERİ 7 20 BRANDALI
SAMSUN 7 20 BRANDALI
ANTALYA 7 20 BRANDALI
İZMİR ÖDEMİŞ 7 20 BRANDALI"""

    test_case(msg1, "MIXED 7.20 AND PALLET LOADS")
    test_case(msg2, "LARGE LIST WITH '7 20' FORMAT")
