import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.utils.city_district_validator import CityDistrictValidator

def test_location():
    validator = CityDistrictValidator()
    
    test_cases = [
        ("İZMİR", "KEMALPAŞA"),
        ("ANKARA", "TEMELLİ"),
        ("", "TEMELLİ"),  # Global lookup test
        ("İZMİR", "BORNOVA"),
        ("İST", "PENDİK")  # Fuzzy city test
    ]
    
    print("\n--- LOKASYON DOĞRULAMA TESTİ (PARAMETRELİ) ---\n")
    
    for city, district in test_cases:
        print(f"Girdi: İl='{city}', İlçe/Mahalle='{district}'")
        res_city, res_dist = validator.validate(city, district)
        print(f"Sonuç: {res_city} / {res_dist}")
        print("-" * 30)

if __name__ == "__main__":
    test_location()
