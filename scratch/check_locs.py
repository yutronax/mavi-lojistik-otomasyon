import os
import sys

# Add current directory to path
sys.path.insert(0, os.getcwd())

from src.utils.city_district_validator import CityDistrictValidator

v = CityDistrictValidator()
print(f"KIZILTEPE check: {v.validate('MARDİN', 'KIZILTEPE')}")
print(f"ANTEP check: {v.validate('GAZİANTEP', 'MERKEZ')}")
print(f"ANTEP alias check: {v.city_aliases.get('ANTEP')}")
