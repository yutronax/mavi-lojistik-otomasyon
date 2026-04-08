import sys
import os
sys.path.insert(0, os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

# Reload rules if needed (VehicleTypeMatcher loads on init)
matcher = VehicleTypeMatcher()

test_cases = [
    "1 PALET",
    "PARÇA",
    "PARCA",
    "1360 PARÇA",
    "1360 PALET",
    "PARÇA PALET",
    "PALET PARÇA",
    "KAPAK YÜKÜ",
    "KAPAK PALET"
]

print("="*60)
print("TESTING PARÇA VS PALET MATCHING")
print("="*60)

for msg in test_cases:
    print(f"\nInput: '{msg}'")
    match = matcher.find_match(msg)
    if match:
        print(f"Match: {match.get('YÜKÜN TİPİ')} | {match.get('ARAÇ TİPİ')}")
        print(f"Confidence: {match.get('confidence', 'N/A')}")
        # Assuming matcher returns the matched rule internally or we can infer from output
        # If we had access to the rule name, it would be better.
    else:
        print("NO MATCH")
