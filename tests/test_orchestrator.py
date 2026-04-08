
import os
import sys
import json
import time
from datetime import datetime

# Proje kök dizinini ekle
PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from src.parsers.veri_cekici_ayristirici import OrchestratorSDK, process_unprocessed_messages

def inject_test_message():
    message_file = os.path.join(PROJECT_ROOT, 'mesajlar.json')
    
    # Mevcut mesajları yükle
    if os.path.exists(message_file):
        with open(message_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'messages': []}
    
    # Test mesajı oluştur
    test_id = f"TEST-INJECT-{int(time.time())}"
    test_msg = {
        "id": test_id,
        "body": f"TEST YUKU {int(time.time())} ADANA VEZİRKÖPRÜ 1360 TIR ACİL",
        "timestamp": time.time(),
        "timestamp_readable": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "chat_id": "TEST_CHAT_ID",
        "chat_name": "TEST GROUP",
        "sender_name": "TestBot",
        "from": "0000000000@s.whatsapp.net",
        "type": "text",
        "is_processed": False
    }
    
    data['messages'].append(test_msg)
    
    with open(message_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Test mesajı inject edildi (ID: {test_id})")
    return test_id

if __name__ == "__main__":
    print("🚀 Test başlatılıyor...")
    msg_id = inject_test_message()
    
    print("⚙️ Orchestrator run_once başlatılıyor...")
    process_unprocessed_messages(keep_only_today=True, run_once=True)
    
    print("🔍 Sonuç kontrol ediliyor...")
    processed_file = os.path.join(PROJECT_ROOT, 'onaylanmamis_ayristirilmis.json')
    if os.path.exists(processed_file):
        with open(processed_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        found = False
        for res in results:
            if res.get('message_id') == msg_id:
                print(f"🎯 BAŞARILI: Mesaj ayrıştırıldı! Sonuç: {json.dumps(res['shipments'], ensure_ascii=False)}")
                found = True
                break
        
        if not found:
            print("❌ HATA: Mesaj işlenemedi (veya filtreye takıldı).")
    else:
        print("❌ HATA: Sonuç dosyası bulunamadı.")
