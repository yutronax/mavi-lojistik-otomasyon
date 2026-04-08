
import unittest
import sys
import os
import logging

# Add project root
sys.path.insert(0, os.getcwd())

from src.utils.city_district_validator import CityDistrictValidator
from src.utils.vehicle_type_matcher import VehicleTypeMatcher
from src.parsers.group_based_parser import GroupBasedParser

logging.basicConfig(level=logging.INFO)

class TestEnhancements(unittest.TestCase):
    
    def setUp(self):
        self.city_validator = CityDistrictValidator()
        self.vehicle_matcher = VehicleTypeMatcher()

    def test_city_fuzzy_correction(self):
        # Case: TIRE -> TİRE -> İZMİR (Unique district reverse lookup)
        city, dist = self.city_validator.validate("İZMİR", "TIRE")
        print(f"\n[Test City] TIRE -> {city}, {dist}")
        self.assertEqual(city, "İZMİR")
        self.assertEqual(dist, "TİRE")

        # Case: Wrong City + Correct District (Pendik is Istanbul)
        city, dist = self.city_validator.validate("ANKARA", "PENDİK")
        print(f"[Test City] ANKARA-PENDİK -> {city}, {dist}")
        self.assertEqual(city, "İSTANBUL")
        self.assertEqual(dist, "PENDİK")

    def test_vehicle_type_matching(self):
        # Case: "TIR brandali"
        # json rules: "BRANDALI" -> KAPALI
        msg = "ISTANBUL ANKARA TIR BRANDALI"
        match = self.vehicle_matcher.find_match(msg)
        print(f"\n[Test Vehicle] '{msg}' -> {match}")
        # Note: 'TIR BRANDALI' isn't a single token in json, but 'BRANDALI' is.
        # Let's see if we match 'BRANDALI' (priority might be high)
        # JSON has "BRANDALI" -> KASA TIPI: KAPALI
        
        # Check shipment application
        shipment = {"original_message": msg}
        processed = self.vehicle_matcher.apply_to_shipment(shipment, msg)
        print(f"[Test Vehicle Applied] {processed}")
        
        self.assertIn("KAPALI", processed.get('kasa_tipi', []))

    def test_parser_integration(self):
        parser = GroupBasedParser()
        # Mock a parsed shipment that needs correction
        shipments = [{
            "nereden_il": "İZMİR", "nereden_ilce": "TIRE",
            "nereye_il": "ANKARA", "nereye_ilce": "MERKEZ",
            "arac_tipi": ["1360"], "kasa_tipi": ["AÇIK"]
        }]
        msg = "İZMİR TIRE DAN ANKARA BRANDALI"
        
        print(f"[Test Integration Output] {finalized}")
        
        f = finalized[0]
        try:
            self.assertEqual(f['nereden_ilce'], 'TİRE') # Should be normalized
        except AssertionError as e:
            print(f"FAIL ILCE: {e}")
            raise e

        try:
            self.assertIn('KAPALI', f['kasa_tipi'])      # Should gain KAPALI from BRANDALI
        except AssertionError as e:
            print(f"FAIL KASA: Expected KAPALI in {f['kasa_tipi']}")
            raise e


if __name__ == '__main__':
    unittest.main()
