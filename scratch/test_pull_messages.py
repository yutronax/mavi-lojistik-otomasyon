# -*- coding: utf-8 -*-
import os
import sys
import json
import time
from datetime import datetime

# Proje kök dizinini ekle
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Unicode sorunlarını önlemek için stdout'u UTF-8 olarak ayarla
import io
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

from src.fetchers.whapi_fetcher import fetch_messages_from_group
from src.utils.common import get_user_data_dir

def main():
    print(f"--- Mesaj Çekme Testi Başladı ({datetime.now().strftime('%H:%M:%S')}) ---")
    
    # Kayıtlı grupları yükle
    data_dir = get_user_data_dir()
    chat_groups_file = os.path.join(data_dir, 'chat_groups.json')
    
    if not os.path.exists(chat_groups_file):
        print(f"Hata: {chat_groups_file} bulunamadı!")
        return

    with open(chat_groups_file, 'r', encoding='utf-8') as f:
        groups = json.load(f)
    
    print(f"Toplam {len(groups)} kayıtlı grup bulundu.")
    
    report = []
    report.append(f"# Mesaj Çekme Raporu - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report.append(f"Toplam Grup Sayısı: {len(groups)}\n")

    # Tüm grupları işlemek çok uzun sürebilir, ancak kullanıcı "tüm gruplardan" dedi.
    # API limitlerini korumak için 2 saniye bekleme ekliyoruz.
    
    for i, group in enumerate(groups):
        group_id = group.get('id')
        group_name = group.get('name', 'Bilinmeyen Grup')
        
        print(f"[{i+1}/{len(groups)}] {group_name} ({group_id}) çekiliyor...")
        
        try:
            # Son 5 mesajı çek
            messages = fetch_messages_from_group(group_id, count=5)
            
            group_report = [f"## Grup: {group_name}"]
            group_report.append(f"ID: {group_id}")
            
            if not messages:
                group_report.append("  *Mesaj bulunamadı veya çekilemedi.*")
            else:
                for msg in messages:
                    # Mesaj detaylarını ayıkla
                    sender = msg.get('from_name', msg.get('from', 'Bilinmeyen'))
                    body = ""
                    text_data = msg.get('text')
                    if isinstance(text_data, dict):
                        body = text_data.get('body', '')
                    else:
                        body = msg.get('body', '')
                    
                    timestamp = msg.get('timestamp')
                    time_str = datetime.fromtimestamp(int(timestamp)).strftime('%H:%M:%S') if timestamp else "??:??:??"
                    
                    snippet = body.strip().replace('\n', ' ')[:100]
                    group_report.append(f"- [{time_str}] **{sender}**: {snippet}...")
            
            report.extend(group_report)
            report.append("-" * 30)
            
        except Exception as e:
            print(f"Hata ({group_name}): {e}")
            report.append(f"## Grup: {group_name} (HATA)")
            report.append(f"Hata detayı: {str(e)}")
            report.append("-" * 30)
        
        # Rate limit koruması
        time.sleep(1.5)

    # Raporu kaydet
    report_file = os.path.join(PROJECT_ROOT, 'artifacts', 'mesaj_cekme_raporu.md')
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(report))
    
    print(f"\n--- Test Tamamlandı. Rapor oluşturuldu: {report_file} ---")

if __name__ == "__main__":
    main()
