import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "UZUN KISA",
    "KISA UZUN",
    "UZUN",
    "KISA",
    "860",
    "1360",
    "KISA KASA",
    "UZUN TIR"
]

print("="*60)
print("TESTING UZUN VS KISA MATCHING")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_match(msg)
    if match:
        print(f"Match: {match.get('ARAÇ TİPİ')} | {match.get('KASA TİPİ')}")
        # print(f"Confidence: {match.get('confidence', 'N/A')}")
    else:
        print("NO MATCH")
