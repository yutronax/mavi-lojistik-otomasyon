
import sys
import os
from src.utils.vehicle_type_matcher import VehicleTypeMatcher

# Mock logging to avoid errors
import logging
logging.basicConfig(level=logging.ERROR)

def test_matcher():
    matcher = VehicleTypeMatcher()
    
    test_cases = [
        "1 TIR",
        "2 TIR",
        "İZMİR İSTANBUL 1 TIR",
        "5 TON YÜKÜMÜZ VAR",
        "1 T YÜK",
        "8 TONLUK ARAÇ",
        "8 PALET YÜK"
    ]
    
    print(f"{'Message':<30} | {'Load Type':<20}")
    print("-" * 55)
    
    for msg in test_cases:
        matches = matcher.find_all_matches(msg)
        load_type = matches.get("YÜKÜN TİPİ", "NONE") if matches else "NONE"
        print(f"{msg:<30} | {load_type:<20}")

if __name__ == "__main__":
    test_matcher()
