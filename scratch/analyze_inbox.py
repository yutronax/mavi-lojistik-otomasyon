
import os
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

def analyze_inbox():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    client = MongoClient(mongo_uri)
    db = client["mavi_lojistik"]
    inbox = db["inbox"]
    
    print("Checking INBOX activity...")
    
    # Get total count
    total = inbox.count_documents({})
    print(f"Total messages in inbox: {total}")
    
    if total == 0:
        print("Inbox is empty! Checking raw_group_data...")
        inbox = db["raw_group_data"]
        total = inbox.count_documents({})
        print(f"Total messages in raw_group_data: {total}")

    # Group by group_name to see distribution
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$group_name",
            "last_message": {"$first": "$timestamp"},
            "count": {"$sum": 1},
            "sample_texts": {"$push": "$message_content"}
        }},
        {"$project": {
            "group_name": "$_id",
            "last_message": 1,
            "count": 1,
            "sample_texts": {"$slice": ["$sample_texts", 3]}
        }},
        {"$sort": {"last_message": -1}}
    ]
    
    results = list(inbox.aggregate(pipeline))
    print(f"Active Groups in this collection: {len(results)}")
    
    now = datetime.now()
    one_hour_ago = now - timedelta(hours=1)
    
    print("\n--- GROUP ACTIVITY SAMPLES ---")
    active_now = 0
    for res in results[:30]:
        name = res.get("group_name") or "Unknown"
        ts = res.get("last_message")
        
        dt = None
        if isinstance(ts, str):
            try: dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
            except: pass
        elif isinstance(ts, datetime):
            dt = ts
            
        status = "SILENT"
        if dt and dt > one_hour_ago:
            status = "ACTIVE (Last 1h)"
            active_now += 1
            
        print(f"Group: {str(name)[:30]:<30} | Msgs: {res['count']:<5} | Last: {ts} | {status}")
    
    print(f"\nSummary: {active_now} groups sent messages in the last hour.")

if __name__ == "__main__":
    analyze_inbox()
