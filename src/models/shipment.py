"""
Shipment Model

Data class for logistics shipment records with validation.
"""

from dataclasses import dataclass, field, asdict
from typing import List, Optional, Tuple
from datetime import datetime


@dataclass
class Shipment:
    """
    Represents a single shipment/load record.
    
    Attributes:
        nereden_il: Origin province
        nereden_ilce: Origin district
        nereye_il: Destination province
        nereye_ilce: Destination district
        arac_tipi: List of vehicle types
        kasa_tipi: List of cargo box types
        yuk_tipi: List of cargo types
        fiyat: Price (as string, may include currency)
        telefon: List of contact phone numbers
        aciklama: Additional notes/description
        isim: Company/person name
        created_time: Timestamp when created
    """
    
    # Required fields
    nereden_il: str
    nereden_ilce: str
    nereye_il: str
    nereye_ilce: str
    arac_tipi: List[str] = field(default_factory=list)
    kasa_tipi: List[str] = field(default_factory=list)
    yuk_tipi: List[str] = field(default_factory=list)
    fiyat: str = ""
    telefon: List[str] = field(default_factory=list)
    aciklama: str = ""
    
    # Optional fields
    isim: str = ""
    created_time: Optional[str] = None
    
    def __post_init__(self):
        """Normalize data after initialization"""
        # Strip whitespace from string fields
        self.nereden_il = self.nereden_il.strip() if self.nereden_il else ""
        self.nereden_ilce = self.nereden_ilce.strip() if self.nereden_ilce else ""
        self.nereye_il = self.nereye_il.strip() if self.nereye_il else ""
        self.nereye_ilce = self.nereye_ilce.strip() if self.nereye_ilce else ""
        self.isim = self.isim.strip() if self.isim else ""
        self.fiyat = self.fiyat.strip() if self.fiyat else ""
        self.aciklama = self.aciklama.strip() if self.aciklama else ""
        
        # Ensure lists are lists
        if not isinstance(self.arac_tipi, list):
            self.arac_tipi = [self.arac_tipi] if self.arac_tipi else []
        if not isinstance(self.kasa_tipi, list):
            self.kasa_tipi = [self.kasa_tipi] if self.kasa_tipi else []
        if not isinstance(self.yuk_tipi, list):
            self.yuk_tipi = [self.yuk_tipi] if self.yuk_tipi else []
        if not isinstance(self.telefon, list):
            self.telefon = [self.telefon] if self.telefon else []
        
        # Set created_time if not provided
        if not self.created_time:
            self.created_time = datetime.now().isoformat()
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Shipment':
        """
        Create Shipment from dictionary.
        
        Args:
            data: Dictionary with shipment data
            
        Returns:
            Shipment instance
        """
        # Extract only fields that exist in the dataclass
        valid_fields = {
            k: v for k, v in data.items()
            if k in cls.__annotations__
        }
        return cls(**valid_fields)
    
    def to_dict(self) -> dict:
        """
        Convert Shipment to dictionary.
        
        Returns:
            Dictionary representation
        """
        return asdict(self)
    
    def validate(self) -> Tuple[bool, str]:
        """
        Validate shipment data.
        
        Returns:
            (is_valid, error_message) tuple
        """
        # Check required fields
        if not self.nereden_il:
            return False, "Nereden il zorunlu"
        
        if not self.nereden_ilce:
            return False, "Nereden ilçe zorunlu"
        
        if not self.nereye_il:
            return False, "Nereye il zorunlu"
        
        if not self.nereye_ilce:
            return False, "Nereye ilçe zorunlu"
        
        if not self.isim:
            return False, "Firma adı zorunlu"
        
        # Check at least one contact method
        if not self.telefon or not any(t.strip() for t in self.telefon):
            return False, "En az bir telefon numarası gerekli"
        
        # Validate phone numbers (basic check)
        for phone in self.telefon:
            if phone.strip():
                # Remove common separators
                clean_phone = phone.replace(' ', '').replace('-', '').replace('(', '').replace(')', '')
                # Check if mostly digits
                if not clean_phone.replace('+', '').replace('0', '').isdigit():
                    return False, f"Geçersiz telefon formatı: {phone}"
        
        return True, ""
    
    def get_route_summary(self) -> str:
        """
        Get human-readable route summary.
        
        Returns:
            String like "İstanbul/Kadıköy → Ankara/Çankaya"
        """
        return f"{self.nereden_il}/{self.nereden_ilce} → {self.nereye_il}/{self.nereye_ilce}"
    
    def get_display_name(self) -> str:
        """
        Get display name for UI.
        
        Returns:
            Company name or "Bilinmeyen"
        """
        return self.isim if self.isim else "Bilinmeyen"
    
    def has_price(self) -> bool:
        """Check if shipment has a price"""
        return bool(self.fiyat and self.fiyat.strip())
    
    def get_primary_phone(self) -> str:
        """
        Get primary phone number.
        
        Returns:
            First non-empty phone or empty string
        """
        for phone in self.telefon:
            if phone.strip():
                return phone.strip()
        return ""
    
    def clone(self) -> 'Shipment':
        """
        Create a deep copy of this shipment.
        
        Returns:
            New Shipment instance with same data
        """
        return Shipment.from_dict(self.to_dict())
    
    def __str__(self) -> str:
        """String representation for debugging"""
        return f"Shipment({self.get_route_summary()}, {self.get_display_name()})"
    
    def __repr__(self) -> str:
        """Detailed representation"""
        return (f"Shipment(from={self.nereden_il}/{self.nereden_ilce}, "
                f"to={self.nereye_il}/{self.nereye_ilce}, "
                f"company={self.isim}, "
                f"phone={self.get_primary_phone()})")
