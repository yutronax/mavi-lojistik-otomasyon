
import json
import os
import time
from datetime import datetime

def check_max_date(file_path):
    if not os.path.exists(file_path): return
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    messages = data if isinstance(data, list) else []
    if not messages: return

    max_ts = 0
    latest_msg = None
    
    for m in messages:
        ts = m.get('timestamp', m.get('message_timestamp', 0))
        if ts > max_ts:
            max_ts = ts
            latest_msg = m

    print(f"File: {file_path}")
    print(f"Latest Message Timestamp: {max_ts}")
    if max_ts > 0:
        print(f"Latest Message Date: {datetime.fromtimestamp(max_ts)}")
        body = str(latest_msg.get('body', ''))[:50]
        # Clean for console
        clean_body = "".join([c if ord(c) < 128 else "?" for c in body])
        print(f"Latest Content Sample: {clean_body}...")

if __name__ == "__main__":
    check_max_date("data/islenmemis_mesajlar.json")
    print("-" * 30)
    check_max_date("data/mesajlar.json")
    print("-" * 30)
    check_max_date("data/live_messages.json")
