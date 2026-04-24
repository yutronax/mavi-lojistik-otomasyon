import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.fetchers.whapi_fetcher import fetch_messages_from_group

def test_fetch_messages():
    group_id = "120363401239562768@g.us"
    print(f"\n--- FETCHING MESSAGES FROM GROUP: {group_id} ---\n")
    messages = fetch_messages_from_group(group_id, count=5)
    print(f"Fetched {len(messages)} messages successfully.")
    
    if messages:
        for i, msg in enumerate(messages):
            body = msg.get('text', {}).get('body', '') or msg.get('body', '')
            print(f"[{i+1}] {msg.get('from_name', 'Unknown')}: {body[:50]}...")
    else:
        print("[!] No messages found or error occurred.")

if __name__ == "__main__":
    test_fetch_messages()
