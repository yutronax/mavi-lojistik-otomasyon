import asyncio
import os
import sys
from pathlib import Path

# Proje root dizinini ekle
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from text_gen_parser import TextGenParser

async def test_complex():
    parser = TextGenParser()
    
    # CEVA LOGISTICS TESTİ
    complex_message = """
    *CEVA LOGISTICS*
    *0543 251 61 77*

    *25/04/2026 CUMARTESİ GÜNÜ YÜKLMELİ*

    *BURSA(NİLÜFER)-BİTLİS(AHLAT)*
    13.60 (0-25 TON)

    *BURSA(TEKNOSAB)-EDREMİT+ÇANAKKALE*
    13.60 (0-19 TON)

    *BURSA(NİLÜFER)-KONYA+KONYA*
    13.60 (0-25 TON)

    *BURSA(NİLÜFER)-MANİSA*
    13.60 (0-25 TON) 2 ARAC

    *BURSA(NİLÜFER)+ERZİN.(İLİÇ)+ERZURUM*
    10 TEKER (0-12 TON)
    TIR’A PARCA OLUR

    *BURSA(GÜRSU)-KONYA(KARATAY)*
    13.60 (0-26 TON)

    *BURSA(İNEGOL)-YALOVA*
    13.60 (0-25 TON)
    20.00’E KADAR YÜKLEME VAR

    *BURSA(GÜRSU)-DÜZCE+DÜZCE*
    10 TEKER (0-16 TON),
    TIR’A PARCA OLUR
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
