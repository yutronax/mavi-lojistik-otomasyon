
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.vehicle_type_matcher import VehicleTypeMatcher
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

def test_matcher():
    matcher = VehicleTypeMatcher()
    
    test_cases = [
        ("ACIK", "AÇIK"),      # Fuzzy: Missing cedilla
        ("KAPAL", "KAPALI"),   # Fuzzy: Missing letter
        ("PLT", "PALETLİ"),    # Abbreviation: Explicit rule
        ("KPL", "KAPALI"),     # Abbreviation: Explicit rule
        ("UZUN TİR", "1360"),  # Fuzzy: UZUN TIR typo
        ("10TEKER", "10 TEKER"), # Exact: Bitişik
        ("10 TKR", "10 TEKER"),  # Fuzzy: TKR vs TEKER (dist=2, len=5, sim=0.6 -> Fail? Threshold 0.85) 
                                 # Wait, TKR vs TEKER. dist 2. max_len 5. sim = 1 - 0.4 = 0.6. Fails. 
                                 # We didn't add TKR.
        ("FRİGO", "FRİGO"),    # Exact
        ("FREGO", "FRİGO"),    # Fuzzy: E vs İ. dist 1. len 5. sim 0.8. Fail? Threshold 0.85. 
                               # 1/5 = 0.2 diff. 0.8 similarity. 
                               # If threshold is 0.85, 0.8 fails.
                               # Maybe I should lower threshold to 0.8?
    ]
    
    print("\n--- Testing Matcher ---\n")
    for input_text, expected_keyword in test_cases:
        print(f"Testing: '{input_text}'")
        match = matcher.find_match(input_text)
        if match:
            print(f"  Match Result: {match}")
            # Check if result roughly matches expected
            # Since output is a dict, we just print it.
        else:
            print("  NO MATCH FOUND")
        print("-" * 30)

if __name__ == "__main__":
    test_matcher()
