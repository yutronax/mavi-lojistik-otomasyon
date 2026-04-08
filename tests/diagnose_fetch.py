import os
import sys
import json
from datetime import datetime

# Add project root to path
PROJECT_ROOT = os.getcwd()
sys.path.insert(0, PROJECT_ROOT)

from src.fetchers.whapi_fetcher import fetch_all_messages, sync_to_queue
from src.utils.config import FETCH_HOURS_BACK, WHATSAPP_TOKEN
from src.services.data_service import DataService

def diagnose():
    print(f"--- Diagnostic Start ---")
    print(f"Token: {WHATSAPP_TOKEN[:5]}...{WHATSAPP_TOKEN[-5:]}")
    print(f"Config FETCH_HOURS_BACK: {FETCH_HOURS_BACK}")
    
    ds = DataService(PROJECT_ROOT)
    
    # Test 1: Fetch with 1 hour (current config)
    print(f"\nTest 1: Fetching with 1 hour back...")
    count_1h = fetch_all_messages(hours_back=1.0)
    print(f"Fetched {count_1h} messages in last 1 hour.")
    
    # Test 2: Fetch with 24 hours (expanded for verification)
    print(f"\nTest 2: Fetching with 24 hours back...")
    count_24h = fetch_all_messages(hours_back=24.0)
    print(f"Fetched {count_24h} messages in last 24 hours.")
    
    # Test 3: sync_to_queue
    print(f"\nTest 3: sync_to_queue...")
    added = sync_to_queue()
    print(f"Added {added} messages to queue.")
    
    # Check if processed_contents.json is blocking
    if added == 0 and (count_1h > 0 or count_24h > 0):
        print("\nWARNING: Messages fetched but none added to queue.")
        print("This confirms content-based deduplication is blocking re-fetches.")
        print("ACTION: You must delete 'data/processed_contents.json' for a full reset.")
        
    print(f"\n--- Diagnostic End ---")

if __name__ == "__main__":
    diagnose()
