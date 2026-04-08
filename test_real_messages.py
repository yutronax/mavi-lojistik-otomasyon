import sys
import os
import json
sys.path.insert(0, os.getcwd())
from text_gen_parser_optimized import TextGenParser

def find_messages(count=10):
    messages_path = os.path.join('data', 'mesajlar.json')
    with open(messages_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    all_msgs = data.get('messages', [])
    
    # 1. Paletli Seramik
    seramik_msgs = [m['body'] for m in all_msgs if 'body' in m and 'paletli' in m['body'].lower() and 'seramik' in m['body'].lower()]
    
    # 2. 7 Paletli / 2 Paletli
    pallet_count_msgs = [m['body'] for m in all_msgs if 'body' in m and ('7 palet' in m['body'].lower() or '2 palet' in m['body'].lower())]
    
    # 3. Genel Paletli
    general_pallet = [m['body'] for m in all_msgs if 'body' in m and 'palet' in m['body'].lower() and m['body'] not in seramik_msgs and m['body'] not in pallet_count_msgs]
    
    selected = (seramik_msgs[:4] + pallet_count_msgs[:4] + general_pallet[:2])[:count]
    return selected

def run_test():
    msgs = find_messages(10)
    print(f"Found {len(msgs)} real messages for testing.\n")
    
    parser = TextGenParser()
    
    for i, msg in enumerate(msgs, 1):
        print("\n" + "=" * 80)
        print(f"TEST CASE {i}: REAL MESSAGE")
        print("=" * 80)
        print(f"MESSAGE:\n{msg}\n")
        
        results = parser.parse(msg)
        
        print("-" * 80)
        print(f"✓ Parsed {len(results)} routes")
        for j, r in enumerate(results, 1):
            print(f"[Route {j}]")
            print(f"  {r['nereden_il']}/{r['nereden_ilce']} → {r['nereye_il']}/{r['nereye_ilce']}")
            print(f"  Araç: {' + '.join(r['arac_tipi'])}")
            print(f"  Kasa: {' + '.join(r['kasa_tipi'])}")
            print(f"  Yük : {' + '.join(r['yuk_tipi'])}")
        print("-" * 80)

if __name__ == "__main__":
    run_test()
