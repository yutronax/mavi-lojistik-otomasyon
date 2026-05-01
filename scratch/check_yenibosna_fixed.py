import os
import sys
sys.path.insert(0, os.getcwd())
from src.utils.city_district_validator import CityDistrictValidator

v = CityDistrictValidator()
# Normalize Yenibosna
norm_yb = v.normalize('YENİBOSNA')
print(f"Normalized: {norm_yb}")

# Check in manual neighborhoods
if norm_yb in v.manual_neighborhoods:
    print(f"Found in manual: {v.manual_neighborhoods[norm_yb]}")
else:
    print("Not found in manual_neighborhoods.")

# Check in general neighborhood map (if loaded)
# Need to trigger loading first
v.validate('İSTANBUL', 'MERKEZ') 
if norm_yb in v.neighborhood_map:
    print(f"Found in neighborhood_map: {v.neighborhood_map[norm_yb]}")
else:
    print("Not found in neighborhood_map.")
