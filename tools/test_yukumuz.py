import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "YÜKÜMÜZ VAR",
    "YÜKÜSTÜ LAZIM",
    "YÜKÜMÜZ PARÇA",
    "YÜKÜSTÜ PARÇA",
    "KONYADAN YÜKÜMÜZ",
    "KONYA YÜKÜSTÜ"
]

print("="*60)
print("TESTING YÜKÜMÜZ VS YÜKÜSTÜ")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_all_matches(msg)
    if match:
        print(f"Match: {match}")
    else:
        print("NO MATCH")
