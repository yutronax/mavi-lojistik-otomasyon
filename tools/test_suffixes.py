import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "AÇIKTIR",
    "KAPALIDIR",
    "FRİGODUR",
    "PALETLİDİR",
    "ACIKTIR",  # Typo + Suffix
    "KAPALIDR", # Typo matches suffix?
    "1360 AÇIKTIR"
]

print("="*60)
print("TESTING SUFFIX HANDLING")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_all_matches(msg)
    if match:
        print(f"Match: {match}")
    else:
        print("NO MATCH")
