# -*- coding: utf-8 -*-
"""
Mavi Lojistik - Filtreleme Analiz Scripti

Bu script, bir WhatsApp grubundan gelen son mesajların neden sisteme düşmediğini
(hangi filtreye takıldığını) detaylı olarak raporlar.
"""

import os
import sys
import json
import time
from datetime import datetime, timedelta

# Proje kök dizinini sys.path'e ekle
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.services.data_service import DataService
from src.utils.human_behavior import HumanBehaviorModel
from src.fetchers.whapi_fetcher import fetch_messages_from_group, convert_whapi_message

def analyze_filtering(group_id=None):
    data_service = DataService(PROJECT_ROOT)
    behavior_model = HumanBehaviorModel()
    
    # Emoji destekli çıktı için sys.stdout'u ayarla
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    # Grup seç
    if not group_id:
        groups = data_service.load_saved_groups()
        if not groups:
            print("❌ Kayıtlı grup bulunamadı.")
            return
        # Mesaj trafiği en yoğun olanlardan birini seçelim (örn: ilk grup)
        group = groups[0]
        group_id = group.get('id')
        group_name = group.get('name')
    else:
        group_name = group_id

    print(f"\n🔍 ANALİZ BAŞLIYOR: {group_name} ({group_id})")
    print("="*60)
    
    # 1. Ham Mesajları Çek (Behavior filtreleri olmadan)
    print(f"📥 Whapi'den son 100 mesaj çekiliyor...")
    raw_messages = fetch_messages_from_group(group_id, count=100)
    
    if not raw_messages:
        print("❌ Mesaj çekilemedi.")
        return

    print(f"✅ {len(raw_messages)} ham mesaj alındı.")
    
    # Analiz Sayaçları
    stats = {
        'total': len(raw_messages),
        'passed': 0,
        'id_handled': 0,
        'body_duplicate': 0,
        'human_skip_latest': 0,
        'human_ignore_last_5': 0,
        'human_cancel_click': 0,
        'shipment_duplicate': 0,
        'blacklist': 0,
        'empty_body': 0
    }

    # Behavior Model Durumları (Bir kez hesaplayalım)
    do_not_reach_latest = behavior_model.should_not_reach_latest()
    ignore_last_5 = behavior_model.should_ignore_last_5_messages()
    
    print(f"\n🤖 Mevcut Behavior Modu (Şans Eseri):")
    print(f"- En son mesajları atla: {'EVET' if do_not_reach_latest else 'HAYIR'}")
    print(f"- Son 5 mesajı görmezden gel: {'EVET' if ignore_last_5 else 'HAYIR'}")
    print("-" * 30)

    # Mesajları tarihe göre sırala (Yeni -> Eski)
    raw_messages.sort(key=lambda x: int(x.get('timestamp', 0)), reverse=True)

    # Human Behavior Listesi Modifikasyonu
    if do_not_reach_latest:
        skip_count = 3 # Ortalama 3 diyelim
        human_messages = raw_messages[skip_count:]
        stats['human_skip_latest'] += skip_count
    else:
        human_messages = raw_messages

    if ignore_last_5:
        human_messages = human_messages[5:]
        stats['human_ignore_last_5'] += 5

    human_message_ids = {m.get('id') for m in human_messages}

    blacklist = data_service.load_blacklist()

    report = []

    for i, msg in enumerate(raw_messages):
        mid = msg.get('id')
        body = msg.get('text', {}).get('body', '') or msg.get('body', '')
        sender = msg.get('from', '')
        
        status = "GEÇTİ ✅"
        reason = ""

        # 1. Boş Mesaj
        if not body or not body.strip():
            status = "ELENDİ ❌"
            reason = "Boş Mesaj"
            stats['empty_body'] += 1
        
        # 2. Blacklist
        elif sender in blacklist:
            status = "ELENDİ ❌"
            reason = "Kara Liste (Blacklist)"
            stats['blacklist'] += 1

        # 3. ID Handled (Zaten işlenmiş)
        elif data_service.is_id_handled(mid):
            status = "ELENDİ ❌"
            reason = "ID Zaten İşlenmiş (24s)"
            stats['id_handled'] += 1

        # 4. Human Behavior
        elif mid not in human_message_ids:
            status = "ELENDİ ❌"
            reason = "İnsan Davranışı (Skip Latest/Ignore Last 5)"
            # Stats zaten yukarıda eklendi
        
        # 5. Body Duplicate (12 saat)
        elif data_service.is_body_known(body):
            status = "ELENDİ ❌"
            reason = "Kopya İçerik (12s - Body Duplicate)"
            stats['body_duplicate'] += 1

        # 6. Shipment Duplicate (24 saat - Rota/Tel)
        else:
            # Parse etmemiz gerekiyor
            converted = convert_whapi_message(msg, {'id': group_id, 'name': group_name})
            if converted:
                from src.parsers.production_parser import ProductionParser
                parser = ProductionParser()
                shipments = parser.parse_message(converted['body'], group_name)
                
                is_dup = False
                for s in shipments:
                    if data_service.is_shipment_duplicate(s):
                        is_dup = True
                        break
                
                if is_dup:
                    status = "ELENDİ ❌"
                    reason = "Mükerrer İlan (24s - Rota/Tel Duplicate)"
                    stats['shipment_duplicate'] += 1
                else:
                    stats['passed'] += 1
            else:
                status = "ELENDİ ❌"
                reason = "Dönüştürme Hatası"

        if i < 20: # Sadece ilk 20 mesajı detaylı yazdıralım
            snippet = body[:40].replace('\n', ' ')
            print(f"[{i+1}] {mid[:10]}... | {status} | {reason if reason else 'OK'} | {snippet}")

    print("\n" + "="*60)
    print("📊 ÖZET RAPOR (Son 100 Mesaj)")
    print("="*60)
    print(f"Toplam Mesaj:        {stats['total']}")
    print(f"Sisteme Düşen:       {stats['passed']}  <-- KRİTİK")
    print("-" * 30)
    print(f"ID Filtresi:         {stats['id_handled']}")
    print(f"Kopya İçerik (Body): {stats['body_duplicate']}")
    print(f"Mükerrer İlan (Rota):{stats['shipment_duplicate']}")
    print(f"İnsan Davranışı:     {stats['human_skip_latest'] + stats['human_ignore_last_5']}")
    print(f"Kara Liste:          {stats['blacklist']}")
    print(f"Boş/Geçersiz:        {stats['empty_body']}")
    print("="*60)

if __name__ == "__main__":
    # Eğer argüman verilmişse o grubu analiz et
    target_id = sys.argv[1] if len(sys.argv) > 1 else None
    analyze_filtering(target_id)
