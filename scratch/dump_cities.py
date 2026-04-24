import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.utils.city_district_validator import CityDistrictValidator

def dump_cities():
    validator = CityDistrictValidator()
    cities = sorted(list(validator.city_map.keys()))
    print(f"Total Cities: {len(cities)}")
    print(f"Sample Cities: {cities[:10]}")
    
    if "İZMİR" in cities:
        print("İZMİR is in the map.")
        districts = sorted(list(validator.city_map["İZMİR"]))
        print(f"İZMİR Districts: {districts}")
    else:
        print("İZMİR is NOT in the map.")
        # Find something similar
        for c in cities:
            if "ZM" in c:
                print(f"Found similar: {c}")

    if "ANKARA" in cities:
        print("ANKARA is in the map.")
    else:
        print("ANKARA is NOT in the map.")

if __name__ == "__main__":
    dump_cities()
