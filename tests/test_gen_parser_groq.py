
import os
import sys
import json
import asyncio
from dotenv import load_dotenv

# Path ayarları
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.append(root_dir)

# Env yükle
load_dotenv(os.path.join(root_dir, '.env'))

import logging

# Logging ayarları
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TestGenParser")

from src.fetchers.mavi_whap import extract_shipments_with_openai
from src.utils.api_key_manager import get_default_manager

def test_parser():
    print("\n--- GROQ GEN PARSER TESTİ BAŞLIYOR ---")
    
    # Test mesajları
    test_messages = [
        {
            "id": "test_1",
            "body": "İSTANBUL - ANKARA 13.60 TENTELİ ACİL YÜK"
        },
        {
            "id": "test_2",
            "body": "KOCAELİ ÇAYIROVA --> BURSA İNEGÖL\nARAÇ: ONTEKER\nYÜK: MOBİLYA\nFİYAT: 8500 TL"
        }
    ]
    
    manager = get_default_manager(root_dir)
    print(f"Aktif Key Index: {manager.get_active_index()}")
    
    for msg in test_messages:
        print(f"\n[ Mesaj İşleniyor: {msg['id']} ]")
        print(f"İçerik: {msg['body']}")
        
        try:
            results = extract_shipments_with_openai(
                msg, 
                model_name="llama-3.1-8b-instant"
            )
            
            if results:
                print(f"SONUÇ: {len(results)} sevkiyat bulundu.")
                for i, s in enumerate(results):
                    print(f"  {i+1}. {s.get('nereden', '?')} -> {s.get('nereye', '?')} | {s.get('yuk_tipi', 'Yük Belirsiz')}")
            else:
                print("SONUÇ: Sevkiyat bulunamadı.")
        except Exception as e:
            print(f"HATA: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    test_parser()
