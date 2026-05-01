import json
import re
import os
from datetime import datetime, timedelta

def check_groups():
    groups_file = r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\data\chat_groups.json'
    log_file = r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\tools\orchestrator.log'
    
    if not os.path.exists(groups_file):
        print(f"Error: {groups_file} not found")
        return
    if not os.path.exists(log_file):
        print(f"Error: {log_file} not found")
        return
        
    with open(groups_file, 'r', encoding='utf-8') as f:
        registered_groups = json.load(f)
    
    # Get the last hour log entries
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    
    fetched_ids = set()
    
    with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            if 'fetched from' in line:
                # Extract date from line start: 2026-04-28 00:35:41,638
                match_date = re.match(r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})', line)
                if match_date:
                    log_date = datetime.strptime(match_date.group(1), '%Y-%m-%d %H:%M:%S')
                    if log_date > one_hour_ago:
                        match_id = re.search(r'fetched from ([\w\.-]+)@g\.us', line)
                        if match_id:
                            fetched_ids.add(match_id.group(1))
    
    print(f"Toplam Kayıtlı Grup: {len(registered_groups)}")
    print(f"Son 1 Saatte Erişilen Benzersiz Grup (Logdan): {len(fetched_ids)}")
    print("-" * 30)
    
    accessible = []
    not_accessible = []
    
    for g in registered_groups:
        gid = g['id'].split('@')[0]
        if gid in fetched_ids:
            accessible.append(g['name'])
        else:
            not_accessible.append(g['name'])
            
    # Use ASCII for printing names to avoid console encoding issues
    def safe_print(name):
        try:
            print(f" - {name}")
        except UnicodeEncodeError:
            print(f" - {name.encode('ascii', 'ignore').decode('ascii')}")

    print(f"Son 1 Saatte Erişilebilen Kayıtlı Gruplar ({len(accessible)}):")
    for name in accessible[:15]:
        safe_print(name)
    if len(accessible) > 15:
        print(f" ... ve {len(accessible)-15} tane daha.")
        
    print(f"\nHenüz Erişilemeyen/Taranmayan Kayıtlı Gruplar ({len(not_accessible)}):")
    for name in not_accessible[:15]:
        safe_print(name)
    if len(not_accessible) > 15:
        print(f" ... ve {len(not_accessible)-15} tane daha.")

if __name__ == "__main__":
    check_groups()
