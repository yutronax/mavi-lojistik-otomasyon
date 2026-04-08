import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

matcher = VehicleTypeMatcher()

test_cases = [
    "1360 FRİGO",
    "1360 KAPALI",
    "1360 FRIGO",
    "1360 KAPALİ",
    "13.60 FRİGO",
    "TERMOKİN HIR",  # Typos
    "FRIGORIFIK",
    "KAPALI FRİGO"
]

print("="*60)
print("TESTING FRIGO VS KAPALI MATCHING")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_match(msg)
    if match:
        print(f"Match: {match.get('ARAÇ TİPİ')} | {match.get('KASA TİPİ')}")
        print(f"Confidence: {match.get('confidence', 'N/A')}")
        print(f"Rule: {match.get('matched_token', 'N/A')}")
    else:
        print("NO MATCH")
