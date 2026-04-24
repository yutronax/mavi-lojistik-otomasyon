import sys
import os
import json
import random
import time

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.fetchers.whapi_fetcher import fetch_messages_from_group, check_health

def mass_test_fetching():
    print("\n--- TOPLU VERI CEKME TESTI (RANDOM 10 GRUP) ---\n")
    
    # Check health first
    try:
        health = check_health()
        status_raw = health.get('status', {})
        status_text = status_raw.get('text', 'unknown') if isinstance(status_raw, dict) else str(status_raw)
        print(f"Sistem Durumu: {status_text.upper()}\n")
    except Exception as e:
        print(f"Health check hatasi: {e}")
    
    # Load registered groups
    groups_path = "data/chat_groups.json"
    if not os.path.exists(groups_path):
        print(f"Hata: {groups_path} bulunamadı!")
        return
        
    with open(groups_path, 'r', encoding='utf-8') as f:
        all_groups = json.load(f)
    
    # Pick 10 random groups
    test_groups = random.sample(all_groups, min(10, len(all_groups)))
    
    success_count = 0
    total_messages = 0
    
    for i, group in enumerate(test_groups):
        g_id = group.get('id')
        g_name = group.get('name', 'Bilinmeyen')
        
        # Strip non-ascii for terminal safety
        safe_name = g_name.encode('ascii', 'ignore').decode('ascii')
        if not safe_name: safe_name = "Group_" + str(i)

        print(f"[{i+1}/10] Cekiliyor: {safe_name} ({g_id})")
        try:
            messages = fetch_messages_from_group(g_id, count=3)
            if messages:
                print(f"   OK: {len(messages)} mesaj alindi.")
                success_count += 1
                total_messages += len(messages)
            else:
                print("   UYARI: Mesaj bulunamadi veya yetki yok.")
        except Exception as e:
            print(f"   HATA: {e}")
        
        time.sleep(1) # Rate limit koruması
        
    print("\n" + "="*40)
    print(f"TEST SONUCU: {success_count}/10 grup basariyla cevap verdi.")
    print(f"Toplam cekilen mesaj: {total_messages}")
    print("="*40)

if __name__ == "__main__":
    mass_test_fetching()
