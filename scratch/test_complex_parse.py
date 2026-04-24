import asyncio
import os
import sys
from pathlib import Path

# Proje root dizinini ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from text_gen_parser import TextGenParser

async def test_complex():
    parser = TextGenParser()
    
    # TOKAT BAL NAKLİYAT TESTİ
    complex_message = """
    *TOKAT BAL NAKLİYAT*
    SİVAS➡️ANKARA TIR hafif
    SİVAS➡️İNEGÖL TIR hafif
    TOKAT SARIGÖL TIR -2
    TOKAT RİZE TIR
    TOKAT ALAŞEHİR 10-12 TON BİG BAG ÇUVALLI MALZEME
    TOKAT KASTAMONU AÇIK TIR

    ÇORUM BAYAT➡️TOKAT AÇIK TIR

    05322531160
    CEM BAL
    """
    
    print("\n--- TEST BAŞLIYOR ---")
    print(f"Mesaj Uzunluğu: {len(complex_message)} karakter")
    
    # 1. Aşama: Temizlik ve Etiketleme Testi
    clean_msg = parser._clean_message(complex_message)
    print("\n[1] TEMİZLENMİŞ VE ETİKETLENMİŞ METİN:")
    print("-" * 30)
    print(clean_msg)
    print("-" * 30)
    
    # 2. Aşama: AI Ayrıştırma Testi
    print("\n[2] AI AYRIŞTIRMA BAŞLIYOR (Stage 1 + Stage 2)...")
    results = await parser.parse_async(complex_message)
    
    print(f"\n[3] BULUNAN ROTA SAYISI: {len(results)}")
    for i, r in enumerate(results, 1):
        print(f"\n--- ROTA #{i} ---")
        print(f"Çıkış: {r.get('nereden_il')} / {r.get('nereden_ilce')}")
        print(f"Varış: {r.get('nereye_il')} / {r.get('nereye_ilce')}")
        print(f"Araç: {r.get('arac_tipi')} | Kasa: {r.get('kasa_tipi')}")
        print(f"Yük: {r.get('yuk_tipi')} | Telefon: {r.get('telefon')}")

if __name__ == "__main__":
    asyncio.run(test_complex())
