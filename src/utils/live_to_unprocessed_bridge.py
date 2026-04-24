
import json
import os
import time
from datetime import datetime
import hashlib

def generate_message_id(chat_name, body, timestamp):
    # Unique ID based on content and time
    raw = f"{chat_name}{body}{timestamp}"
    return hashlib.md5(raw.encode('utf-8')).hexdigest()

def bridge_live_to_unprocessed():
    live_path = "data/live_messages.json"
    unprocessed_path = "data/islenmemis_mesajlar.json"
    
    if not os.path.exists(live_path):
        print("Live messages file not found.")
        return

    # Load Live
    with open(live_path, 'r', encoding='utf-8') as f:
        live_data = json.load(f)
    
    # Load Unprocessed (if exists)
    unprocessed_data = []
    existing_ids = set()
    if os.path.exists(unprocessed_path):
        try:
            with open(unprocessed_path, 'r', encoding='utf-8') as f:
                unprocessed_data = json.load(f)
                # Track existing IDs to prevent duplicates
                for msg in unprocessed_data:
                    existing_ids.add(msg.get('id', ''))
        except:
            unprocessed_data = []

    print(f"Current unprocessed count: {len(unprocessed_data)}")
    print(f"New live messages to check: {len(live_data)}")

    added_count = 0
    for live_msg in live_data:
        # Map fields
        chat_name = live_msg.get('group', 'Unknown Group')
        body = live_msg.get('body', '')
        ts = live_msg.get('timestamp', time.time())
        sender = live_msg.get('sender', 'Unknown')
        
        # Generate format compatible with main app
        msg_id = generate_message_id(chat_name, body, ts)
        
        if msg_id in existing_ids:
            continue
            
        new_msg = {
            "id": msg_id,
            "body": body,
            "timestamp": int(ts),
            "timestamp_readable": datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S'),
            "chat_id": f"live_{chat_name}", # Simulated ID
            "chat_name": chat_name,
            "sender_name": sender,
            "from": "0000000000", # Placeholder
            "type": "text",
            "is_processed": False
        }
        
        unprocessed_data.append(new_msg)
        existing_ids.add(msg_id)
        added_count += 1

    if added_count > 0:
        # Sort by timestamp (newest first)
        unprocessed_data.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Save back
        with open(unprocessed_path, 'w', encoding='utf-8') as f:
            json.dump(unprocessed_data, f, ensure_ascii=False, indent=4)
        
        print(f"✅ SUCCESS: {added_count} new messages transferred to main app.")
    else:
        print("ℹ️ No new messages found to transfer.")

if __name__ == "__main__":
    bridge_live_to_unprocessed()
