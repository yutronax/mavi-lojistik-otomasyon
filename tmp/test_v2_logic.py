import sys
import os
import json

# Add src to path
sys.path.append(os.getcwd())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

def test_v2():
    matcher = VehicleTypeMatcher()
    
    test_cases = [
        "TIR FRİGO",
        "1360 AÇIK",
        "860 DAMPERLİ",
        "TIR",
        "YÜKÜMÜZ SERAMİK"
    ]
    
    print("=== LIVE V2 LOGIC TEST ===")
    for msg in test_cases:
        # Get rules as text_gen_parser does
        rules = matcher.get_relevant_rules(msg)
        print(f"\nMessage: {msg}")
        if rules:
            # Sort rules by priority to see who wins (assuming parser picks top one)
            sorted_rules = sorted(rules, key=lambda x: x['priority'], reverse=True)
            top = sorted_rules[0]
            print(f"  Top Rule Picked: {top['pattern']} (Priority: {top['priority']})")
            print(f"  Output: {top['output']}")
        else:
            print("  No rules matched.")

if __name__ == "__main__":
    test_v2()
