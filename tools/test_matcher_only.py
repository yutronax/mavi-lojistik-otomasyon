
import sys
import os
import json

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

def test_matcher():
    matcher = VehicleTypeMatcher()
    
    inputs = [
        "13/60",
        "13 / 60",
        "13.60",
        "Ankara 13/60 yükü",
        "13/60 860", # Control
        "60" # Control
    ]
    
    print(f"Loaded {len(matcher.rules)} rules.")
    
    for text in inputs:
        print(f"\nInput: '{text}'")
        matches = matcher.find_all_matches(text)
        print("Matches components:")
        # unpack sets
        # The return is a Dict with found_vehicles (List[Set]), found_bodies...
        # Wait, find_all_matches return signature in code I viewed was Dict... let's check code.
        # Actually I didn't see the return statement of find_all_matches in previous view.
        # Assuming it returns a dict-like structure or single best? 
        # Ah, code line 191 says "Returns a merged dictionary...".
        # Let's just print the whole result.
        print(matches)

if __name__ == "__main__":
    test_matcher()
