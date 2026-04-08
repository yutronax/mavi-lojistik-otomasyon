import sys
import os
import json
from datetime import datetime

# Proje root dizinini ekle
PROJECT_ROOT = r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik'
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from tools.submit_approved_loads import YukBuradaSubmitter

def dry_run_test():
    print("--- YükBurada Submitter Dry Run Test ---")
    
    # Gerçek API'ya gitmemesi için mock veya basit bir kontrol yapabiliriz
    # Ancak transform_record_to_payload metodunu test etmek güvenli
    submitter = YukBuradaSubmitter()
    
    test_record = {
        "nereden_il": "İSTANBUL",
        "nereden_ilce": "Tuzla",
        "nereye_il": "ANKARA",
        "nereye_ilce": "Polatlı",
        "yuk_tipi": "KOMPLE",
        "arac_tipi": ["Tir"],
        "telefon": "05321234567",
        "orijinal_mesaj": "İstanbul Tuzla -> Ankara Polatlı Komple Tir 05321234567"
    }
    
    print("\n[1] Record Transformation Testi:")
    payload = submitter.transform_record_to_payload(test_record)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # Beklenen alanları kontrol et
    required_fields = ["pickupCity", "pickupIlce", "deliveryCity", "deliveryIlce", "loadType", "requiredVehicleTypes", "_phone"]
    missing = [f for f in required_fields if f not in payload]
    
    if not missing:
        print("\n✅ Payload dönüşümü başarılı. Tüm zorunlu alanlar mevcut.")
    else:
        print(f"\n❌ Eksik alanlar: {missing}")

    print("\n[2] Auth Check (Sadece Bilgi):")
    print(f"Master Phone: {submitter.master_phone}")
    print(f"API Base URL: {submitter.api_base_url}")

if __name__ == "__main__":
    dry_run_test()
