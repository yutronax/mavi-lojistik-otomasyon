import pytest
from src.domain.entities.shipment import Shipment

def test_shipment_creation():
    """Temel shipment oluşturma"""
    shipment = Shipment(
        nereden_il="ANKARA",
        nereye_il="İSTANBUL",
        message_id="test_123"
    )
    
    assert shipment.nereden_il == "ANKARA"
    assert shipment.nereye_il == "İSTANBUL"
    assert shipment.nereden_ilce == "MERKEZ"  # Default
    assert shipment.arac_tipi == ["1360"]  # Default

def test_shipment_validation():
    """Validasyon testleri"""
    # Geçerli shipment
    valid = Shipment(
        nereden_il="ANKARA",
        nereye_il="İSTANBUL",
        message_id="test_123"
    )
    assert valid.validate() is True
    
    # Geçersiz - nereden_il yok
    invalid = Shipment(
        nereden_il="",
        nereye_il="İSTANBUL",
        message_id="test_123"
    )
    assert invalid.validate() is False

def test_shipment_completeness():
    """Tamamlanmışlık testi"""
    # Tam dolu
    complete = Shipment(
        nereden_il="ANKARA",
        nereden_ilce="YENİMAHALLE",
        nereye_il="İSTANBUL",
        nereye_ilce="TUZLA",
        arac_tipi=["1360"],
        kasa_tipi=["KAPALI"],
        yuk_tipi=["KOMPLE"],
        telefon="0532 123 45 67",
        message_id="test_123"
    )
    assert complete.is_complete() is True
    
    # Eksik (telefon yok)
    incomplete = Shipment(
        nereden_il="ANKARA",
        nereye_il="İSTANBUL",
        message_id="test_123"
    )
    assert incomplete.is_complete() is False

def test_shipment_dict_conversion():
    """Dict dönüşümü"""
    shipment = Shipment(
        nereden_il="ANKARA",
        nereye_il="İSTANBUL",
        message_id="test_123"
    )
    
    # To dict
    data = shipment.to_dict()
    assert isinstance(data, dict)
    assert data['nereden_il'] == "ANKARA"
    assert 'created_at' not in data  # Metadata çıkarıldı
    
    # From dict
    restored = Shipment.from_dict(data)
    assert restored.nereden_il == "ANKARA"
    assert restored.nereye_il == "İSTANBUL"
