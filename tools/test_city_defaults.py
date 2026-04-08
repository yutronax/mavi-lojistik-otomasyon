
import sys
import os
import logging

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.city_district_validator import CityDistrictValidator

# Configure logging
logging.basicConfig(level=logging.INFO)

def test_defaults():
    validator = CityDistrictValidator()
    
    test_cases = [
        # City, District, Expected City, Expected District
        ("ADANA", "MERKEZ", "ADANA", "ÇUKUROVA"), # Default from JSON
        ("ANKARA", "", "ANKARA", "YENİMAHALLE"), # Default from JSON
        ("DİYARBAKIR", "MERKEZ", "DİYARBAKIR", "SUR"), # Updated JSON default
        ("İSTANBUL ANADOLU", "MERKEZ", "İSTANBUL", "MALTEPE"), # Special Logic
        ("İSTANBUL AVRUPA", "", "İSTANBUL", "AVCILAR"), # Special Logic
        ("İSTANBUL", "MERKEZ", "İSTANBUL", "AVCILAR"), # Standard Default for Istanbul
        ("İSTANBUL ANADOLU", "PENDİK", "İSTANBUL", "PENDİK"), # Explicit district preserved
        ("MOĞLA", "MERKEZ", "MUĞLA", "ORTACA"), # Fuzzy City + Default
    ]
    
    print("\n--- Testing City Defaults ---\n")
    all_passed = True
    
    for city, dist, exp_city, exp_dist in test_cases:
        res_city, res_dist = validator.validate(city, dist)
        
        # Normalize for comparison
        res_city = validator._normalize(res_city)
        res_dist = validator._normalize(res_dist)
        exp_city = validator._normalize(exp_city)
        exp_dist = validator._normalize(exp_dist)
        
        match = (res_city == exp_city and res_dist == exp_dist)
        status = "PASS" if match else "FAIL"
        if not match: 
            all_passed = False
            
        print(f"[{status}] Input: ('{city}', '{dist}') -> Got: ('{res_city}', '{res_dist}') | Expected: ('{exp_city}', '{exp_dist}')")
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED")
    else:
        print("\n❌ SOME TESTS FAILED")

if __name__ == "__main__":
    test_defaults()
