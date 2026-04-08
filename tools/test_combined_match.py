import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "1360 kırk ayak 10 teker",   # Should match all 3
    "Frigo paletli farketmez",   # Should match Frigo + Paletli
    "1360 FRİGO",                # Should match specific 1360 Frigo rule (1200) - single output
    "1360 KAPALI",               # Should match 1360 Kapalı rule (500)
    "1360 AÇIK",                 # Should match 1360 Açık rule (500)
    "KAPALI AÇIK",               # Should combine
    "10 TEKER KAMYON",           # 10 TEKER + KAMYON (if separate)
    "UZUN KISA",                 # Should be just 1360 (due to recent fix)
    "PARÇA PALET",               # Should be Paletli (due to recent fix)
    "1360 AÇIK FRİGODA OLUR",    # Edge case: Specific 1360 + Generic Frigo
    "1360 FRİGO DA OLUR"         # Variation
]

print("="*60)
print("TESTING COMBINED MATCHING LOGIC")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_all_matches(msg)
    if match:
        print(f"Match: {match}")
    else:
        print("NO MATCH")
