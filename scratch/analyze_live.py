
import json
import os
import time
from datetime import datetime, timedelta

def analyze_live():
    file_path = "data/live_messages.json"
    if not os.path.exists(file_path): return
    
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    messages = data if isinstance(data, list) else []
    total = len(messages)
    
    now = time.time()
    one_hour_ago = now - 3600
    
    active_in_last_hour = 0
    group_distribution = {}
    
    for m in messages:
        ts = m.get('timestamp', m.get('message_timestamp', 0))
        if ts > one_hour_ago:
            active_in_last_hour += 1
            g_name = m.get('chat_name', m.get('group_name', 'Unknown'))
            group_distribution[g_name] = group_distribution.get(g_name, 0) + 1

    print(f"File: {file_path}")
    print(f"Total entries: {total}")
    print(f"Messages in LAST HOUR: {active_in_last_hour}")
    print("-" * 30)
    print("Group Distribution in last hour:")
    for g, count in sorted(group_distribution.items(), key=lambda x: x[1], reverse=True)[:10]:
        clean_g = "".join([c if ord(c) < 128 else "?" for c in str(g)])
        print(f" - {clean_g}: {count}")

if __name__ == "__main__":
    analyze_live()
