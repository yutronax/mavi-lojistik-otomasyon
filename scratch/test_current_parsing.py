#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Test the current parser with the user's exact message to see errors."""

import sys
import os
import json
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from text_gen_parser import TextGenParser

test_message = """ANKARA ➡️ YÜKLER :
Sakarya Ferizli.      :600+
İst.Tuzla.                  :850+
İst.Ataşehir.            :850+
İst.Arnavutköy.     :1.150+
İst.Göztepe.            :820+
İzmir Dikili.              :1.050+
13.60 Tır
⬇️
GEMEREK ERCİYES YÜKLER:
Vezirköprü.          :900+
Sungurlu.              :550+
Gümüşhacıköyü.:610+
Ordu merkez.      :1.000+
Amasya merkez.  :550+
Niksar merkez.     :600.+
Sivas merkez.      :360+
Elazığ merkez.     :900+
13.60 Tır
⬇️
BATMAN ORGANİZE YÜKLER:
Urfa merkez.      :370+
13.60 Tır
⬇️
ÇANKIRI KURŞUNLU YÜKLER:
Akhisar +Saruhanlı:35.000₺
KDV-DAHİL 13.60 Tır

SaygınEr lojistik 
05302926776"""

EXPECTED_ROUTES = [
    # Section 1: ANKARA -> X
    {"nereden_il": "ANKARA", "nereye_il": "SAKARYA", "nereye_ilce": "FERİZLİ"},
    {"nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "nereye_ilce": "TUZLA"},
    {"nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "nereye_ilce": "ATAŞEHİR"},
    {"nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "nereye_ilce": "ARNAVUTKÖY"},
    {"nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "nereye_ilce": "GÖZTEPE"},
    {"nereden_il": "ANKARA", "nereye_il": "İZMİR", "nereye_ilce": "DİKİLİ"},
    
    # Section 2: SİVAS GEMEREK -> X
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "SAMSUN", "nereye_ilce": "VEZİRKÖPRÜ"},
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "ÇORUM", "nereye_ilce": "SUNGURLU"},
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "AMASYA", "nereye_ilce": "GÜMÜŞHACIKÖY"},
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "ORDU"},
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "AMASYA"},
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "TOKAT", "nereye_ilce": "NİKSAR"},
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "SİVAS"},
    {"nereden_il": "SİVAS", "nereden_ilce": "GEMEREK", "nereye_il": "ELAZIĞ"},
    
    # Section 3: BATMAN -> X
    {"nereden_il": "BATMAN", "nereye_il": "ŞANLIURFA"},
    
    # Section 4: ÇANKIRI KURŞUNLU -> X
    {"nereden_il": "ÇANKIRI", "nereden_ilce": "KURŞUNLU", "nereye_il": "MANİSA", "nereye_ilce": "AKHİSAR"},
    {"nereden_il": "ÇANKIRI", "nereden_ilce": "KURŞUNLU", "nereye_il": "MANİSA", "nereye_ilce": "SARUHANLI"},
]

async def main():
    parser = TextGenParser()
    
    print("=" * 80)
    print("CLEAN MESSAGE RESULT:")
    print("=" * 80)
    clean = parser._clean_message(test_message)
    print(clean)
    
    print("\n" + "=" * 80)
    print("PARSING WITH AI...")
    print("=" * 80)
    
    results = await parser.parse_async(test_message)
    
    print(f"\n[RESULT] {len(results)} routes found\n")
    
    for i, r in enumerate(results, 1):
        print(f"[Route {i}] {r.get('nereden_il','?')}/{r.get('nereden_ilce','?')} -> {r.get('nereye_il','?')}/{r.get('nereye_ilce','?')}")
    
    # Compare with expected
    print("\n" + "=" * 80)
    print("EXPECTED vs ACTUAL COMPARISON:")
    print("=" * 80)
    
    print(f"Expected: {len(EXPECTED_ROUTES)} routes")
    print(f"Got:      {len(results)} routes")
    
    # Save raw results for analysis
    with open('scratch/test_current_results.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    print("\nResults saved to scratch/test_current_results.json")

if __name__ == "__main__":
    asyncio.run(main())
