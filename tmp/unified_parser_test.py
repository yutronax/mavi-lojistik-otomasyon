import sys
import os
import json
import re

# 1. Add project root to path BEFORE anything else
sys.path.insert(0, os.getcwd())

# 2. Force UTF-8 for terminal output if on Windows
if sys.platform == "win32":
    import codecs
    if hasattr(sys.stdout, 'detach'):
        sys.stdout = codecs.getwriter("utf-8")(sys.stdout.detach())

from src.utils.vehicle_type_matcher import VehicleTypeMatcher
from src.utils.advanced_location_matcher import LocationMatcher
from src.utils.phone_utils import normalize_phone

def extract_phones(text: str):
    pattern = r'(?:0\s?)?5[0-9]{2}\s?[0-9]{3}\s?[0-9]{2}\s?[0-9]{2}|(?:0\s?)?5[0-9]{2}\s?[0-9]{7}'
    matches = re.findall(pattern, text)
    return [normalize_phone(m) for m in matches]

def run_unified_test(limit=10):
    data_path = "data/onaylanan_kayitlar.json"
    if not os.path.exists(data_path):
        print("Data not found.")
        return

    vt_matcher = VehicleTypeMatcher()
    loc_matcher = LocationMatcher()

    with open(data_path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    # Use a set to track unique messages to ensure diversity
    selected_msgs = []
    seen_bodies = set()
    
    # Iterate through records and pick diverse ones
    for r in records:
        body = (r.get('message_info', {}).get('body') or 
                r.get('orijinal_mesaj') or 
                r.get('aciklama') or "").strip()
        
        if len(body) > 40 and body[:40] not in seen_bodies:
            selected_msgs.append(body)
            seen_bodies.add(body[:40])
            
        if len(selected_msgs) >= limit:
            break

    print(f"\n--- 10 Farklı Mesaj Üzerinde Birleşik Ayrıştırma Analizi ---\n")

    for i, msg in enumerate(selected_msgs, 1):
        # Clean for display
        display_msg = msg[:100].replace('\n', ' ')
        print(f"ÖRNEK #{i}:")
        print(f"MESAJ: {display_msg}...")
        
        vt = vt_matcher.find_all_matches(msg)
        loc = loc_matcher.validate_and_fix(None, None, msg)
        phones = extract_phones(msg)

        print(f"  > ARAÇ/KASA : {vt.get('ARAÇ TİPİ', '-')} | {vt.get('KASA TİPİ', '-')}")
        print(f"  > YÜK TİPİ  : {vt.get('YÜKÜN TİPİ', '-')}")
        print(f"  > KONUM     : {loc.get('il', '-')}/{loc.get('ilce', '-')} (Hassasiyet: {loc.get('confidence', 0):.2f})")
        print(f"  > TELEFON   : {', '.join(phones) if phones else '-'}")
        print("-" * 60)

if __name__ == "__main__":
    run_unified_test()
