import json
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
data_file = os.path.join(PROJECT_ROOT, 'data', 'onaylanmamis_ayristirilmis.json')

def analyze():
    if not os.path.exists(data_file):
        print("Dosya bulunamadı.")
        return
        
    with open(data_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    results = []
    count = 0
    for item in data:
        if item.get('invalid_location'):
            msg_id = item.get('message_id', 'Bilinmiyor')
            body = item.get('body') or item.get('message_info', {}).get('body', '')
            
            routes = []
            for s in item.get('shipments', []):
                nereden = s.get('nereden_il', 'BOS')
                nereye = s.get('nereye_il', 'BOS')
                routes.append(f"{nereden} -> {nereye}")
            
            results.append({
                "id": msg_id,
                "mesaj": body[:200],
                "rotalar": routes
            })
            count += 1
            if count >= 10:
                break
                
    with open('scratch/invalid_analysis.json', 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    analyze()
