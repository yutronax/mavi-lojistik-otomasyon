import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "KISA DORSE",        # Expected: Vehicle=860, Body=DAMPERLİ, Load=DÖKME
    "1 PALET",           # Expected: Load=PARÇA (previously PALETLİ)
    "FRİGO",             # Expected: Load=PARÇA (previously PALETLİ)
    "1360 FRİGO",        # Expected: Load=PARÇA
    "KISA DORSE YÜKÜ",   # Expected: Same as KISA DORSE
]

print("="*60)
print("TESTING KISA DORSE & PALET CHANGE")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_all_matches(msg)
    if match:
        print(f"Result: {match}")
    else:
        print("NO MATCH")
