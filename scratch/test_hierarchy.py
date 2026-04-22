import sys
import os

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.city_district_validator import CityDistrictValidator

def test_validator():
    validator = CityDistrictValidator()
    
    test_cases = [
        # (City, District, Expected_City, Expected_Dist, Comment)
        ("ANKARA", "EMİRLİ", "ANKARA", "GÖLBAŞI", "Neighborhood in Ankara should be found because Ankara is matched first"),
        ("ANKARA", "PENDİK", "ANKARA", "MERKEZ", "District from another city (Pendik/Istanbul) should NOT hijack Ankara. Returns default."),
        ("İSTANBUL", "BULGURLU", "İSTANBUL", "ÜSKÜDAR", "Neighborhood in Istanbul"),
        ("", "PENDİK", "İSTANBUL", "PENDİK", "Unique district reverse lookup"),
        ("RİZE", "VİZE", "RİZE", "MERKEZ", "Rize is a city, Vize is a district in Kirklareli. Should not hijack Rize."),
        ("KONYA", "SELÇUKLU", "KONYA", "SELÇUKLU", "Exact match"),
        ("AFYON", "MERKEZ", "AFYONKARAHİSAR", "MERKEZ", "Alias match"),
    ]
    
    print("\n--- LOCATION VALIDATION TEST (STRICT HIERARCHY) ---\n")
    passed = 0
    for c, d, ex_c, ex_d, comment in test_cases:
        res_c, res_d = validator.validate(c, d)
        status = "PASS" if res_c == ex_c and res_d == ex_d else "FAIL"
        if status == "PASS": passed += 1
        
        print(f"Input:    {c} / {d}")
        print(f"Result:   {res_c} / {res_d}")
        print(f"Expected: {ex_c} / {ex_d}")
        print(f"Status:   {status} - {comment}\n")
    
    print(f"Total: {passed}/{len(test_cases)} tests passed.")

if __name__ == "__main__":
    test_validator()
