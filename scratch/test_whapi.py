import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.fetchers.whapi_fetcher import check_health, fetch_groups

def test_connection():
    print("\n--- WHAPI CONNECTION HEALTH CHECK ---\n")
    health = check_health()
    print(f"Health Status: {json.dumps(health, indent=2)}")
    
    status_raw = health.get('status', {})
    if isinstance(status_raw, dict):
        status_text = str(status_raw.get('text', 'unknown')).lower()
    else:
        status_text = str(status_raw).lower()

    if status_text in ['auth', 'connected', 'active']:
        print(f"\n--- WHATSAPP IS CONNECTED (Status: {status_text.upper()}) ---\n")
        print("\n--- FETCHING GROUPS (TEST) ---\n")
        groups = fetch_groups(max_count=5)
        print(f"Fetched {len(groups)} groups successfully.")
        if groups:
            print(f"Sample Group: {groups[0].get('name')} ({groups[0].get('id')})")
    else:
        print("\n[!] CRITICAL: Whapi is NOT connected or authorized.")

if __name__ == "__main__":
    test_connection()
