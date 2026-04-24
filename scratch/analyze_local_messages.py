
import json
import os
import time
from datetime import datetime, timedelta

def analyze_local_file(file_path):
    if not os.path.exists(file_path):
        print(f"Error: {file_path} not found!")
        return

    print(f"Analyzing {file_path}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Failed to read JSON: {e}")
        return

    # Assuming data is a list of messages or a dict with messages
    messages = []
    if isinstance(data, list):
        messages = data
    elif isinstance(data, dict):
        # Look for a list inside
        for k, v in data.items():
            if isinstance(v, list):
                messages = v
                break

    total = len(messages)
    print(f"Total entries in file: {total}")
    
    if total == 0:
        return

    now = time.time()
    one_hour_ago = now - 3600
    
    # Analyze distribution
    group_counts = {}
    active_in_last_hour = 0
    
    print("\n--- SAMPLE ENTRIES ---")
    for msg in messages[-10:]: # Look at last 10
        body = str(msg.get('body', msg.get('message_content', '')))[:50]
        ts = msg.get('timestamp', msg.get('message_timestamp', 0))
        g_name = msg.get('chat_name', msg.get('group_name', 'Unknown'))
        
        dt = datetime.fromtimestamp(ts) if ts > 0 else "Unknown"
        print(f"Time: {dt} | Group: {g_name[:20]:<20} | Text: {body}...")

    # Calculate statistics
    for msg in messages:
        ts = msg.get('timestamp', msg.get('message_timestamp', 0))
        g_name = msg.get('chat_name', msg.get('group_name', 'Unknown'))
        
        group_counts[g_name] = group_counts.get(g_name, 0) + 1
        if ts > one_hour_ago:
            active_in_last_hour += 1

    print("-" * 50)
    print(f"SUMMARY:")
    print(f" - Active messages in the last 1 hour: {active_now if 'active_now' in locals() else active_in_last_hour}")
    print(f" - Total Unique Groups in file: {len(group_counts)}")
    
    # Top 5 groups
    sorted_groups = sorted(group_counts.items(), key=lambda x: x[1], reverse=True)
    print("\nTop 5 Groups in this file:")
    for name, count in sorted_groups[:5]:
        print(f" - {name}: {count} msgs")

if __name__ == "__main__":
    analyze_local_file("data/islenmemis_mesajlar.json")
