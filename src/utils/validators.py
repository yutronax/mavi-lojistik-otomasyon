# -*- coding: utf-8 -*-
"""
Validasyon fonksiyonları
"""
import re
from typing import Dict, List, Optional, Tuple, Any


def validate_phone(phone: str) -> Tuple[bool, str]:
    """
    Telefon numarasını validate eder.
    
    Args:
        phone: Kontrol edilecek telefon numarası
        
    Returns:
        Tuple[bool, str]: (Geçerli mi, Hata mesajı veya temiz numara)
    """
    if not phone:
        return False, "Telefon numarası boş"
    
    # Sadece rakamları al
    digits = re.sub(r'\D', '', str(phone))
    
    # Uzunluk kontrolü
    if len(digits) < 10:
        return False, "Telefon numarası çok kısa"
    
    if len(digits) > 12:
        return False, "Telefon numarası çok uzun"
    
    # Türkiye formatına çevir
    if digits.startswith('90') and len(digits) == 12:
        clean_phone = digits
    elif digits.startswith('0') and len(digits) == 11:
        clean_phone = '90' + digits[1:]
    elif len(digits) == 10:
        clean_phone = '90' + digits
    else:
        return False, "Geçersiz telefon formatı"
    
    return True, clean_phone


def validate_location(location: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Lokasyon bilgisini validate eder.
    
    Args:
        location: Lokasyon dictionary'si (il, ilce alanları)
        
    Returns:
        Tuple[bool, List[str]]: (Geçerli mi, Hata listesi)
    """
    errors = []
    
    if not location:
        return False, ["Lokasyon bilgisi boş"]
    
    il = location.get('il', '').strip() if location.get('il') else ''
    
    if not il:
        errors.append("İl bilgisi eksik")
    
    # İlçe zorunlu değil ama varsa kontrol et
    ilce = location.get('ilce', '').strip() if location.get('ilce') else ''
    
    return len(errors) == 0, errors


def validate_shipment(shipment: Dict[str, Any]) -> Tuple[bool, List[str]]:
    """
    Sevkiyat bilgisini validate eder.
    
    Args:
        shipment: Sevkiyat dictionary'si
        
    Returns:
        Tuple[bool, List[str]]: (Geçerli mi, Hata listesi)
    """
    errors = []
    
    if not shipment:
        return False, ["Sevkiyat bilgisi boş"]
    
    # Yükleme lokasyonu kontrolü
    yukleme = shipment.get('yukleme_il') or shipment.get('yukleme', {}).get('il')
    if not yukleme:
        errors.append("Yükleme ili eksik")
    
    # Boşaltma lokasyonu kontrolü
    bosaltma = shipment.get('bosaltma_il') or shipment.get('bosaltma', {}).get('il')
    if not bosaltma:
        errors.append("Boşaltma ili eksik")
    
    # En az yükleme veya boşaltma olmalı
    if not yukleme and not bosaltma:
        errors.append("Yükleme veya boşaltma lokasyonu gerekli")
    
    return len(errors) == 0, errors


def validate_date_format(date_str: str) -> Tuple[bool, str]:
    """
    Tarih formatını validate eder.
    
    Args:
        date_str: Tarih stringi
        
    Returns:
        Tuple[bool, str]: (Geçerli mi, Hata mesajı veya normalize edilmiş tarih)
    """
    if not date_str:
        return True, ""  # Tarih opsiyonel
    
    # Desteklenen formatlar
    formats = [
        r'^\d{4}-\d{2}-\d{2}$',  # YYYY-MM-DD
        r'^\d{2}/\d{2}/\d{4}$',  # DD/MM/YYYY
        r'^\d{2}\.\d{2}\.\d{4}$',  # DD.MM.YYYY
    ]
    
    for pattern in formats:
        if re.match(pattern, date_str):
            return True, date_str
    
    return False, "Geçersiz tarih formatı"


def validate_required_fields(data: Dict[str, Any], required: List[str]) -> Tuple[bool, List[str]]:
    """
    Zorunlu alanları kontrol eder.
    
    Args:
        data: Kontrol edilecek dictionary
        required: Zorunlu alan listesi
        
    Returns:
        Tuple[bool, List[str]]: (Geçerli mi, Eksik alan listesi)
    """
    missing = []
    
    for field in required:
        value = data.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    
    return len(missing) == 0, missing
