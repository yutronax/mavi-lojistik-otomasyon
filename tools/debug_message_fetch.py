
import sys
import os
import json
import requests
import logging

# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add src to path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.utils.config import FETCH_HOURS_BACK
from dotenv import load_dotenv

load_dotenv()
WHAPI_TOKEN = os.getenv('WHATSAPP_TOKEN')
WHAPI_BASE_URL = "https://gate.whapi.cloud"

def fetch_messages_debug(group_id):
    url = f"{WHAPI_BASE_URL}/messages/list/{group_id}"
    params = {
        "count": 20
    }
    headers = {
        "Authorization": f"Bearer {WHAPI_TOKEN}",
        "Accept": "application/json"
    }
    
    logger.info(f"Fetching messages for group: {group_id}")
    logger.info(f"URL: {url}")
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        logger.info(f"Status Code: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            messages = data.get('messages', [])
            logger.info(f"Message count: {len(messages)}")
            if messages:
                logger.info("First message sample:")
                logger.info(json.dumps(messages[0], indent=2, ensure_ascii=False))
        else:
            logger.error(f"Error response: {response.text}")
            
    except Exception as e:
        logger.error(f"Exception: {e}")

if __name__ == "__main__":
    # Use one of the group IDs seen in previous logs
    TEST_GROUP_ID = "120363294210157315@g.us" 
    fetch_messages_debug(TEST_GROUP_ID)
