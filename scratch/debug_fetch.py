import requests
import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.utils.config import WHATSAPP_TOKEN

def debug_group_fetch():
    group_id = "120363421972115030@g.us"
    url = f"https://gate.whapi.cloud/messages/list/{group_id}?count=3"
    headers = {
        'accept': 'application/json',
        'Authorization': f'Bearer {WHATSAPP_TOKEN}'
    }
    
    print(f"DEBUG: Requesting {url}")
    response = requests.get(url, headers=headers)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")

if __name__ == "__main__":
    debug_group_fetch()
