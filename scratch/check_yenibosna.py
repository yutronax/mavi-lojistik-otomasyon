import os
import sys
sys.path.insert(0, os.getcwd())
from src.utils.city_district_validator import CityDistrictValidator

v = CityDistrictValidator()
res = v.validate_neighborhood('YENİBOSNA')
print(f"Yenibosna search: {res}")

# Check if it exists in any city
found = False
for city, districts in v.data.items():
    for dist, neighborhoods in districts.items():
        if 'YENİBOSNA' in [n.upper() for n in neighborhoods]:
            print(f"Found in {city} / {dist}")
            found = True

if not found:
    print("YENİBOSNA not found in official database.")
