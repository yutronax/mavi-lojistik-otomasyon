import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "KAPALI TIR",         # Expected: Vehicle=1360, Body=KAPALI (NOT AÇIK + KAPALI)
    "PARÇA TIR",          # Expected: Vehicle=1360 (NOT 10 TEKER etc.)
    "1360 PARÇA",         # Expected: Vehicle=1360
    "KAPALI DORSE",       # Expected: Body=KAPALI
    "AÇIK TIR"            # Expected: Vehicle=1360, Body=AÇIK
]

print("="*60)
print("TESTING MERGE/INTERSECTION LOGIC")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_all_matches(msg)
    if match:
        print(f"Result: {match}")
    else:
        print("NO MATCH")
