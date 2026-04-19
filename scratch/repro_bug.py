
import os
import sys

# Path setup
sys.path.insert(0, os.getcwd())

from src.utils.city_district_validator import CityDistrictValidator

def test_repro():
    validator = CityDistrictValidator()
    
    # Test Adana without district
    city, dist = validator.validate("ADANA", "")
    print(f"Input: ADANA, '' -> Result: {city}, {dist}")
    
    # Test Ankara without district
    city, dist = validator.validate("ANKARA", "")
    print(f"Input: ANKARA, '' -> Result: {city}, {dist}")

    # Test Istanbul without district
    city, dist = validator.validate("İSTANBUL", "")
    print(f"Input: İSTANBUL, '' -> Result: {city}, {dist}")

if __name__ == "__main__":
    test_repro()
