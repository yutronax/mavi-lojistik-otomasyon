import sys
import os
sys.path.insert(0, os.getcwd())
from src.utils.city_district_validator import CityDistrictValidator

v = CityDistrictValidator()
term = "EMİRLİ"
term_norm = v._normalize(term)

print(f"Term: {term_norm}")
if term_norm in v.neighborhood_map:
    print(f"Found in neighborhood_map: {v.neighborhood_map[term_norm]}")
else:
    print("NOT found in neighborhood_map")

print(f"Total neighborhoods: {len(v.neighborhood_map)}")
print(f"Default district for ANKARA: {v.default_districts.get('ANKARA')}")
