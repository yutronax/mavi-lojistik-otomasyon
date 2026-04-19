import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()
uri = os.getenv('MONGODB_URI')
if not uri:
    print("MONGODB_URI not found!")
    exit(1)

try:
    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    db = client.get_database('mavi_lojistik')
    
    # Check Inbox
    inbox = db.get_collection('inbox')
    last_inbox = inbox.find().sort("message_timestamp", -1).limit(5)
    
    print("--- LAST 5 INBOX MESSAGES ---")
    for doc in last_inbox:
        if not doc: continue
        doc.pop('_id', None)
        ts = doc.get('message_timestamp')
        try:
            dt = datetime.fromtimestamp(float(ts)) if ts else "N/A"
        except:
            dt = "Invalid TS"
        print(f"[{dt}] ID: {doc.get('message_id')} - From: {doc.get('phone')} - Text: {str(doc.get('body'))[:50]}...")
    
    # Check Approved Shipments
    shipments = db.get_collection('approved_shipments')
    last_shipments = shipments.find().sort("approved_at", -1).limit(5)
    
    print("\n--- LAST 5 APPROVED SHIPMENTS ---")
    for doc in last_shipments:
        doc.pop('_id', None)
        print(f"[{doc.get('approved_at')}] ID: {doc.get('message_id')} - Route: {doc.get('nereden_il')} -> {doc.get('nereye_il')}")

except Exception as e:
    print(f"Error: {e}")
