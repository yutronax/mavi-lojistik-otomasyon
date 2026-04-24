
import asyncio
import os
from dotenv import load_dotenv
from src.utils.api_key_manager import get_default_manager
from text_gen_parser import TextGenParser

async def test_rotation():
    load_dotenv()
    print("🔍 Sistem Testi Başlıyor (Bekleme ve Rotasyon dahil)...")
    
    manager = get_default_manager()
    manager.load_keys(force_reload=True)
    
    print(f"✅ Google Pool: {len(manager._google_keys)} anahtar")
    print(f"✅ Groq Pool: {len(manager._groq_keys)} anahtar")
    
    parser = TextGenParser()
    # Test mesajı
    test_msg = "AVRUPA YAKASI - ANADOLU YAKASI 13.60"
    
    print("\n🚀 Ayrıştırma başlatılıyor (Lütfen logları takip edin, 429'lar havuzda dönecektir)...")
    results = await parser.parse_async(test_msg)
    
    print("\n📊 SONUÇ TABLOSU:")
    if not results:
        print("❌ Ayrıştırma başarısız oldu (Tüm modeller ve yedekler tükendi).")
    else:
        for res in results:
            origin = f"{res.get('yukleme_yeri_ilce')}/{res.get('yukleme_yeri_il')}"
            dest = f"{res.get('bosaltma_yeri_ilce')}/{res.get('bosaltma_yeri_il')}"
            print(f"📍 {origin} -> {dest} | 💰 {res.get('arac_tipi')}")

if __name__ == "__main__":
    asyncio.run(test_rotation())
