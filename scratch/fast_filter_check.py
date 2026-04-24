# -*- coding: utf-8 -*-
"""
Hızlı Filtreleme Kontrolü (AI Çağrısı Olmadan)
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
from src.fetchers.whapi_fetcher import fetch_messages_from_group

def fast_analyze_filtering(group_id=None):
    data_service = DataService(PROJECT_ROOT)
    behavior_model = HumanBehaviorModel()
    
    # Emoji destekli çıktı için sys.stdout'u ayarla
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')

    # Grup seç
    groups = data_service.load_saved_groups()
    if not groups:
        print("❌ Kayıtlı grup bulunamadı.")
        return
    
    group = groups[0]
    group_id = group.get('id')
    group_name = group.get('name')

    print(f"\n🔍 HIZLI ANALİZ BAŞLIYOR: {group_name} ({group_id})")
    print("="*60)
    
    # 1. Ham Mesajları Çek
    print(f"📥 Whapi'den son 100 mesaj çekiliyor...")
    raw_messages = fetch_messages_from_group(group_id, count=100)
    
    if not raw_messages:
        print("❌ Mesaj çekilemedi.")
        return

    print(f"✅ {len(raw_messages)} ham mesaj alındı.")
    
    stats = {
        'total': len(raw_messages),
        'passed': 0,
        'id_handled': 0,
        'body_duplicate': 0,
        'human_skip_latest': 0,
        'human_ignore_last_5': 0,
        'blacklist': 0,
        'empty_body': 0
    }

    # Behavior Model Durumları
    do_not_reach_latest = behavior_model.should_not_reach_latest()
    ignore_last_5 = behavior_model.should_ignore_last_5_messages()
    
    print(f"\n🤖 Mevcut Behavior Modu (Şans Eseri):")
    print(f"- En son mesajları atla: {'EVET' if do_not_reach_latest else 'HAYIR'}")
    print(f"- Son 5 mesajı görmezden gel: {'EVET' if ignore_last_5 else 'HAYIR'}")
    print("-" * 30)

    raw_messages.sort(key=lambda x: int(x.get('timestamp', 0)), reverse=True)

    # Human Behavior
    if do_not_reach_latest:
        skip_count = 3
        human_messages = raw_messages[skip_count:]
        stats['human_skip_latest'] += skip_count
    else:
        human_messages = raw_messages

    if ignore_last_5:
        human_messages = human_messages[5:]
        stats['human_ignore_last_5'] += 5

    human_message_ids = {m.get('id') for m in human_messages}
    blacklist = data_service.load_blacklist()

    for i, msg in enumerate(raw_messages):
        mid = msg.get('id')
        body = msg.get('text', {}).get('body', '') or msg.get('body', '')
        sender = msg.get('from', '')
        
        status = "GEÇTİ ✅"
        reason = ""

        if not body or not body.strip():
            status = "ELENDİ ❌"
            reason = "Boş Mesaj"
            stats['empty_body'] += 1
        elif sender in blacklist:
            status = "ELENDİ ❌"
            reason = "Kara Liste"
            stats['blacklist'] += 1
        elif data_service.is_id_handled(mid):
            status = "ELENDİ ❌"
            reason = "ID Zaten İşlenmiş"
            stats['id_handled'] += 1
        elif mid not in human_message_ids:
            status = "ELENDİ ❌"
            reason = "İnsan Davranışı"
        elif data_service.is_body_known(body):
            status = "ELENDİ ❌"
            reason = "Kopya İçerik (Body Duplicate)"
            stats['body_duplicate'] += 1
        else:
            stats['passed'] += 1

        if i < 15:
            snippet = body[:40].replace('\n', ' ')
            print(f"[{i+1}] {mid[:10]}... | {status} | {reason if reason else 'OK'} | {snippet}")

    print("\n" + "="*60)
    print("📊 ÖZET RAPOR (AI Çağrısı Olmadan)")
    print("="*60)
    print(f"Toplam Mesaj:        {stats['total']}")
    print(f"Sisteme Düşen:       {stats['passed']}")
    print("-" * 30)
    print(f"ID Filtresi:         {stats['id_handled']}")
    print(f"Kopya İçerik (Body): {stats['body_duplicate']}")
    print(f"İnsan Davranışı:     {stats['human_skip_latest'] + stats['human_ignore_last_5']}")
    print(f"Kara Liste:          {stats['blacklist']}")
    print(f"Boş/Geçersiz:        {stats['empty_body']}")
    print("="*60)

if __name__ == "__main__":
    fast_analyze_filtering()
