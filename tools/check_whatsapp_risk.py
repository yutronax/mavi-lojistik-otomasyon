# -*- coding: utf-8 -*-
"""
check_whatsapp_risk.py

WhatsApp numaranızın Whapi Safety Meter (Risk of Blocking) durumunu kontrol eder.
API üzerinden risk skorlarını çeker ve detayları ekrana yazdırır.
"""
import os
import sys
from datetime import datetime

# Proje kök dizinini yola ekle
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Windows'ta Emoji karakterlerinin yazdırılması için gerekli
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

from src.fetchers.whapi_fetcher import get_channel_risk, calculate_channel_risk

def print_metric(label, value):
    if value is None:
        status = "Bilinmiyor"
        val_str = "N/A"
    else:
        # Yuvarlayarak anlamlandırma yapıyoruz
        rounded_val = round(value)
        meaning = {
            3: "✅ İYİ (Hadi gene iyisin)",
            2: "⚠️ DİKKAT (Biraz yavaşla)",
            1: "🛑 TEHLİKE (Ban kapıda!)"
        }
        status = meaning.get(rounded_val, "Bilinmiyor")
        val_str = f"{value:.2f}" if isinstance(value, float) else str(value)
        
    print(f"{label:<30}: {status} ({val_str})")

def main():
    print("="*60)
    print("🛡️  WHATSAPP BAN RİSKİ ANALİZİ")
    print("="*60)
    
    # Argüman kontrolü
    force_calculate = "--force" in sys.argv
    
    if force_calculate:
        print("🔄 Yeni risk analizi hesaplanıyor...")
        data = calculate_channel_risk()
    else:
        print("📥 Mevcut risk verileri çekiliyor...")
        data = get_channel_risk()
    
    if not data:
        print("❌ Veri alınamadı. Lütfen API token'ınızı ve internet bağlantınızı kontrol edin.")
        return

    print(f"📅 Son Güncelleme: {data.get('lastUpdateDate', 'Bilinmiyor')}")
    print("-" * 60)
    
    risk_factor = data.get('riskFactor')
    print_metric("GENEL RİSK SKORU", risk_factor)
    
    print("-" * 60)
    print_metric("Rehber Kapsama Oranı", data.get('riskFactorContacts'))
    print_metric("Yanıt Verme Oranı", data.get('riskFactorChats'))
    print_metric("Numara Ömrü (Eskilik)", data.get('lifeTime'))
    
    print("=" * 60)
    
    if risk_factor == 1:
        print("\n🆘 TAVSİYE: LÜTFEN AKTİVİTENİZİ ACİLEN AZALTIN!")
        print("- Grup tarama sıklığını düşürün.")
        print("- Manuel mesaj gönderimini durdurun.")
        print("- Numaranızı 'sıcak tutma' (warm-up) moduna alın.")
    elif risk_factor == 2:
        print("\n⚠️ TAVSİYE: Biraz daha dikkatli olunmalı.")
        print("- Bilinmeyen numaralarla etkileşimi azaltın.")
    else:
        print("\n✅ TAVSİYE: Her şey yolunda görünüyor.")
        print("İnsansı davranış modeline uymaya devam edin.")

if __name__ == "__main__":
    main()
