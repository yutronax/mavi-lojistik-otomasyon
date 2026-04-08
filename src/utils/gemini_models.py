from pydantic import BaseModel, Field
from typing import List, Optional


class Shipment(BaseModel):
    isim: Optional[str] = Field('', description="Şahıs/ilan adı")
    nereden_il: str = Field(..., description="Origin province")
    nereden_ilce: str = Field('MERKEZ', description="Origin district")
    nereye_il: str = Field(..., description="Destination province")
    nereye_ilce: str = Field('MERKEZ', description="Destination district")
    arac_tipi: List[str] = Field(default_factory=lambda: ["1360"], description="Vehicle types")
    kasa_tipi: List[str] = Field(default_factory=lambda: ["AÇIK"], description="Kasa/body types")
    yuk_tipi: List[str] = Field(default_factory=lambda: ["KOMPLE"], description="Load types")
    fiyat: Optional[str] = Field('SORUNUZ', description="Price string or 'SORUNUZ'")
    telefon: Optional[str] = Field('', description="Phone number if any")
    aciklama: Optional[str] = Field('', description="Free-text description")
    message_id: Optional[str] = Field('', description="Original message id")


class ShipmentsResponse(BaseModel):
    shipments: List[Shipment]


class ValidationResult(BaseModel):
    ok: bool
    issues: List[str] = Field(default_factory=list)
    confidence: float = Field(0.0, ge=0.0, le=1.0)
