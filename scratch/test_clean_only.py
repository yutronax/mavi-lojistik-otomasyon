#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Quick test of _clean_message only - no AI calls."""

import sys, os
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

parser = TextGenParser()
clean = parser._clean_message(test_message)

print("=" * 80)
print("CLEAN MESSAGE OUTPUT:")
print("=" * 80)
for i, line in enumerate(clean.split('\n'), 1):
    print(f"  {i:3d} | {line}")

print("\n" + "=" * 80)
print("CHECKS:")
print("=" * 80)

# Check separators
sep_count = clean.count('---')
print(f"{'[OK]' if sep_count >= 3 else '[FAIL]'} Section separators (---): {sep_count} found (expected 3)")

# Check İSTANBUL expansion
ist_count = clean.upper().count('İSTANBUL')
print(f"{'[OK]' if ist_count >= 4 else '[FAIL]'} İSTANBUL expanded: {ist_count} times (expected 5)")

# Check price removal
has_prices = ':600' in clean or ':850' in clean or ':1.150' in clean
print(f"{'[OK]' if not has_prices else '[FAIL]'} Price patterns removed: {'YES' if not has_prices else 'NO - PRICES STILL PRESENT'}")

# Check line breaks preserved
line_count = len([l for l in clean.split('\n') if l.strip()])
print(f"{'[OK]' if line_count >= 15 else '[FAIL]'} Line count: {line_count} non-empty lines (expected 15+)")

# Check YÜKLER header
has_header = 'YÜKLER' in clean
has_arrow_header = '-> YÜKLER' in clean
print(f"{'[OK]' if has_header else '[FAIL]'} YÜKLER header present: {has_header}")
print(f"{'[OK]' if not has_arrow_header else '[FAIL]'} Arrow before YÜKLER removed: {'YES' if not has_arrow_header else 'NO'}")
