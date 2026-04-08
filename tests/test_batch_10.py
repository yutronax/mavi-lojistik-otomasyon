
import os
import sys
import json
import time
from datetime import datetime

# Proje kök dizinini ekle
PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from src.parsers.veri_cekici_ayristirici import process_unprocessed_messages

def inject_10_test_messages():
    message_file = os.path.join(PROJECT_ROOT, 'mesajlar.json')
    
    # Mevcut mesajları yükle
    if os.path.exists(message_file):
        with open(message_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        data = {'messages': []}
    
    injected_ids = []
    
    test_locations = [
        ("ADANA", "İSTANBUL"),
        ("ANKARA", "İZMİR"),
        ("BURSA", "ANTALYA"),
        ("KONYA", "SAMSUN"),
        ("KAYSERİ", "MERSİN"),
        ("GAZİANTEP", "DENİZLİ"),
        ("ESKİŞEHİR", "TRABZON"),
        ("DİYARBAKIR", "EDİRNE"),
        ("MALATYA", "MUĞLA"),
        ("ERZURUM", "VAN")
    ]
    
    for i in range(10):
        nereden, nereye = test_locations[i]
        test_id = f"BATCH-TEST-{i}-{int(time.time())}"
        test_msg = {
            "id": test_id,
            "body": f"BATCH {i}: {nereden} {nereye} 1360 TIR ACİL",
            "timestamp": time.time() + i, # Ensure different order
            "timestamp_readable": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            "chat_id": "BATCH_TEST_CHAT",
            "chat_name": "BATCH TEST GROUP",
            "sender_name": f"Tester_{i}",
            "from": f"tester_{i}@s.whatsapp.net",
            "type": "text",
            "is_processed": False
        }
        data['messages'].append(test_msg)
        injected_ids.append(test_id)
        time.sleep(0.01) # Small delay for unique timestamps if needed
    
    with open(message_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"✅ 10 test mesajı inject edildi.")
    return injected_ids

if __name__ == "__main__":
    print("🚀 BATCH 10 TEST başlatılıyor...")
    msg_ids = inject_10_test_messages()
    
    print("⚙️ Orchestrator run_once başlatılıyor (Bekleme dahil)...")
    start_time = time.time()
    process_unprocessed_messages(keep_only_today=True, run_once=True)
    duration = time.time() - start_time
    
    print(f"🔍 İşlem {duration:.2f} saniye sürdü. Sonuçlar kontrol ediliyor...")
    
    processed_file = os.path.join(PROJECT_ROOT, 'onaylanmamis_ayristirilmis.json')
    if os.path.exists(processed_file):
        with open(processed_file, 'r', encoding='utf-8') as f:
            results = json.load(f)
        
        found_count = 0
        for res in results:
            if res.get('message_id') in msg_ids:
                found_count += 1
        
        print(f"🎯 SONUÇ: {found_count}/10 mesaj işlendi.")
        if found_count == 10:
            print("✨ TEST BAŞARILI!")
        else:
            print("⚠️ BAZI MESAJLAR İŞLENEMEDİ.")
    else:
        print("❌ HATA: Sonuç dosyası bulunamadı.")
