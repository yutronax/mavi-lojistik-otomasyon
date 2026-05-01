import json
import os
import logging
from typing import List, Dict, Set, Optional

logger = logging.getLogger(__name__)

class LocationValidator:
    """
    Validates Turkish locations (provinces and districts) using il_ilçe_mahalle.json.
    Used to flag international or unknown shipments.
    """
    
    _instance = None
    _locations: Dict[str, Set[str]] = {}
    _all_cities: Set[str] = set()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(LocationValidator, cls).__new__(cls)
        return cls._instance

    def __init__(self, json_path: Optional[str] = None):
        if not self._locations:
            if not json_path:
                # Default path
                from src.utils.common import get_bundled_data_dir
                json_path = str(get_bundled_data_dir() / 'il_ilçe_mahalle.json')
            
            self._load_locations(json_path)

    def _normalize_text(self, text: str) -> str:
        """Normalizes Turkish characters for robust matching."""
        if not text:
            return ""
        text = text.strip().upper()
        replacements = {
            'İ': 'I', 'I': 'I', 'ı': 'I', 'i': 'I',
            'Ş': 'S', 'ş': 'S', 'S': 'S',
            'Ğ': 'G', 'ğ': 'G', 'G': 'G',
            'Ü': 'U', 'ü': 'U', 'U': 'U',
            'Ö': 'O', 'ö': 'O', 'O': 'O',
            'Ç': 'C', 'ç': 'C', 'C': 'C',
        }
        for search, replace in replacements.items():
            text = text.replace(search, replace)
        return text

    def _load_locations(self, json_path: str):
        """Loads and indexes locations for fast lookup."""
        try:
            if not os.path.exists(json_path):
                logger.error(f"Location file not found: {json_path}")
                return

            with open(json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data:
                city = self._normalize_text(item.get('il', ''))
                if not city:
                    continue
                
                districts = set()
                for d in item.get('ilceler', []):
                    dist_name = self._normalize_text(d.get('ilce', ''))
                    if dist_name:
                        districts.add(dist_name)
                
                self._locations[city] = districts
                self._all_cities.add(city)
            
            logger.info(f"LocationValidator: Loaded {len(self._all_cities)} cities.")
        except Exception as e:
            logger.error(f"Error loading location data: {e}")

    def is_valid_city(self, city: str) -> bool:
        """Checks if the given city exists in Turkey."""
        if not city:
            return False
        return self._normalize_text(city) in self._all_cities

    def is_valid_location(self, city: str, district: Optional[str] = None) -> bool:
        """
        Checks if the city and optionally the district exist in Turkey.
        If district is provided but city is not valid, returns False.
        If only city is provided, checks city validity.
        """
        if not city:
            return False
        
        city_norm = self._normalize_text(city)
        if city_norm not in self._all_cities:
            return False
        
        if district:
            dist_norm = self._normalize_text(district)
            # Some districts might be missing or recorded differently, 
            # but usually they should be in the set.
            return dist_norm in self._locations.get(city_norm, set())
        
        return True

    def validate_shipment(self, shipment: Dict) -> bool:
        """
        Validates origin and destination of a shipment.
        Returns True if both are valid Turkish locations.
        """
        # Validate Origin
        origin_city = shipment.get('nereden_il')
        origin_dist = shipment.get('nereden_ilce')
        
        if not self.is_valid_city(origin_city):
            return False
            
        # Validate Destination
        dest_city = shipment.get('nereye_il')
        dest_dist = shipment.get('nereye_ilce')
        
        if not self.is_valid_city(dest_city):
            return False
            
        return True

    @staticmethod
    def get_validator():
        """Singleton accessor."""
        return LocationValidator()
