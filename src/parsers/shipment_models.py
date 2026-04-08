"""Shipment Pydantic models and helper functions.

This module provides:
- Shipment, ShipmentList (pydantic models)
- validate_type_values(arac_tipi, kasa_tipi, yuk_tipi)
- load_json_file(file_path)
"""
from pydantic import BaseModel, Field
from typing import List, Dict
import os
import json
from src.utils.common import get_root_path
import logging
logger = logging.getLogger(__name__)


class Shipment(BaseModel):
    isim: str = Field(default="", description="Kişi veya firma adı")
    nereden_il: str = Field(..., description="Kalkış ili (BÜYÜK HARF)")
    nereden_ilce: str = Field(default="", description="Kalkış ilçesi")
    nereye_il: str = Field(..., description="Varış ili (BÜYÜK HARF)")
    nereye_ilce: str = Field(default="", description="Varış ilçesi")
    arac_tipi: List[str] = Field(default=["1360"], description="Araç tipi (liste)")
    kasa_tipi: List[str] = Field(default=["AÇIK", "KAPALI"], description="Kasa tipi (liste)")
    yuk_tipi: List[str] = Field(default=["KOMPLE"], description="Yük tipi (liste)")
    fiyat: str = Field(default="SORUNUZ", description="Fiyat bilgisi")
    telefon: str = Field(default="", description="Telefon numarası(ları)")
    aciklama: str = Field(default="", description="Açıklama")
    message_id: str = Field(..., description="Mesaj ID")


class ShipmentList(BaseModel):
    shipments: List[Shipment]


def load_json_file(file_path: str) -> List[Dict]:
    """Load JSON file safely; return [] on error."""
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"[] {file_path} yüklenirken hata: {e}")
        return []


def validate_type_values(arac_tipi: List[str], kasa_tipi: List[str], yuk_tipi: List[str], 
                         valid_types_file: str = None) -> Dict[str, List[str]]:
    """Validate and normalize arac/kasa/yuk tipi lists against data file.

    Falls back to sensible defaults if validation file missing or values invalid.
    """
    if valid_types_file is None:
        root_dir = get_root_path()
        valid_types_file = os.path.join(root_dir, 'data', 'arac_yuk_kasa_tipleri.json')

    valid_types = {
        'arac_tipleri': [],
        'kasa_tipleri': [],
        'yuk_tipleri': []
    }

    try:
        if os.path.exists(valid_types_file):
            with open(valid_types_file, 'r', encoding='utf-8') as f:
                valid_types = json.load(f)
    except Exception as e:
        logger.debug(f"[] arac_yuk_kasa_tipleri.json yüklenemedi: {e}")

    default_arac = ['1360']
    default_kasa = ['AÇIK', 'KAPALI']
    default_yuk = ['KOMPLE']

    valid_arac = [v.strip().upper() for v in valid_types.get('arac_tipleri', [])]
    valid_kasa = [v.strip().upper() for v in valid_types.get('kasa_tipleri', [])]
    valid_yuk = [v.strip().upper() for v in valid_types.get('yuk_tipleri', [])]

    validated_arac = []
    invalid_arac = []
    for tip in arac_tipi:
        tip_upper = str(tip).strip().upper()
        if tip_upper in valid_arac:
            validated_arac.append(tip_upper)
        else:
            invalid_arac.append(tip_upper)

    if not validated_arac:
        validated_arac = default_arac
        if invalid_arac:
            logger.debug(f"[] Geçersiz araç tipleri varsayılanla değiştirildi: {invalid_arac} → {default_arac}")
    elif invalid_arac:
        logger.debug(f"[] Geçersiz araç tipleri filtrelendi: {invalid_arac}")

    validated_kasa = []
    invalid_kasa = []
    for tip in kasa_tipi:
        tip_upper = str(tip).strip().upper()
        if tip_upper in valid_kasa:
            validated_kasa.append(tip_upper)
        else:
            invalid_kasa.append(tip_upper)

    if not validated_kasa:
        validated_kasa = default_kasa
        if invalid_kasa:
            logger.debug(f"[] Geçersiz kasa tipleri varsayılanla değiştirildi: {invalid_kasa} → {default_kasa}")
    elif invalid_kasa:
        logger.debug(f"[] Geçersiz kasa tipleri filtrelendi: {invalid_kasa}")

    validated_yuk = []
    invalid_yuk = []
    for tip in yuk_tipi:
        tip_upper = str(tip).strip().upper()
        if tip_upper in valid_yuk:
            validated_yuk.append(tip_upper)
        else:
            invalid_yuk.append(tip_upper)

    if not validated_yuk:
        validated_yuk = default_yuk
        if invalid_yuk:
            logger.debug(f"[] Geçersiz yük tipleri varsayılanla değiştirildi: {invalid_yuk} → {default_yuk}")
    elif invalid_yuk:
        logger.debug(f"[] Geçersiz yük tipleri filtrelendi: {invalid_yuk}")

    return {
        'arac_tipi': validated_arac,
        'kasa_tipi': validated_kasa,
        'yuk_tipi': validated_yuk
    }
