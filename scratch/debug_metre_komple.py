import os
import sys
import json

# Add src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.utils.vehicle_type_matcher import VehicleTypeMatcher

def debug_matcher():
    matcher = VehicleTypeMatcher()
    message = "AYDIN MERKEZ ZİLE 4 TON 6 METRE AÇIK TIR OLACAK"
    
    print(f"Mesaj: {message}")
    
    # Test 1: Full message match
    result_full = matcher.find_all_matches(message)
    print(f"\nTam mesaj tarama sonucu: {result_full}")
    
    # Test 2: AI'nın bulduğu 'TIR' kelimesiyle tarama (Hatalı olan kısım burasıydı)
    ai_found_type = "TIR"
    result_ai = matcher.find_all_matches(ai_found_type)
    print(f"Sadece AI'nın bulduğu '{ai_found_type}' kelimesiyle tarama sonucu: {result_ai}")

if __name__ == "__main__":
    debug_matcher()
