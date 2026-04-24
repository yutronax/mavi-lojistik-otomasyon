
import os
from pymongo import MongoClient
from dotenv import load_dotenv

def check_raw_and_info():
    load_dotenv()
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["mavi_lojistik"]
    
    print("--- INBOX (message_info) ---")
    inbox_doc = db["inbox"].find_one()
    if inbox_doc and "message_info" in inbox_doc:
        print(f"message_info keys: {inbox_doc['message_info'].keys()}")
        print(f"Group name in info: {inbox_doc['message_info'].get('group_name') or inbox_doc['message_info'].get('group')}")

    print("\n--- RAW_GROUP_DATA ---")
    raw_doc = db["raw_group_data"].find_one()
    if raw_doc:
        print(f"Raw doc keys: {raw_doc.keys()}")
        if "message_info" in raw_doc:
             print(f"Raw message_info keys: {raw_doc['message_info'].keys()}")

if __name__ == "__main__":
    check_raw_and_info()
