import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.utils.city_district_validator import CityDistrictValidator

def test_fuzzy_and_aliases():
    v = CityDistrictValidator()
    
    test_cases = [
        "Maraş Elbistan çıkışlı",
        "Urfa Merkez yükleme",
        "Silibri yükleri",
        "Antep - Maraş arası",
        "Yaman Merkez"
    ]
    
    print("="*60)
    print("DYNAMIC CONTEXT FUZZY & ALIAS TEST")
    print("="*60)
    
    for msg in test_cases:
        print(f"\nMessage: '{msg}'")
        context = v.get_loc_context(msg)
        print(f"Generated Context:\n{context}")
        print("-" * 40)

if __name__ == "__main__":
    test_fuzzy_and_aliases()
