
import os
import time
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

def analyze_groups():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    if not mongo_uri:
        print("Error: MONGODB_URI not found!")
        return

    client = MongoClient(mongo_uri)
    db = client.get_database("mavi_lojistik")
    messages_col = db["messages"]

    print("Analyzing group activity via MongoDB...")

    now = datetime.now()
    last_hour = now - timedelta(hours=1)
    
    # Simple aggregate to get counts and last message per group
    pipeline = [
        {"$sort": {"timestamp": -1}},
        {"$group": {
            "_id": "$group_name",
            "last_date": {"$first": "$timestamp"},
            "total_msgs": {"$sum": 1}
        }},
        {"$sort": {"last_date": -1}}
    ]

    try:
        results = list(messages_col.aggregate(pipeline))
    except Exception as e:
        print(f"Aggregation failed: {e}")
        return

    print(f"Total Groups in DB: {len(results)}")
    print("\n--- TOP 20 MOST RECENT GROUPS ---")
    
    active_count = 0
    for res in results[:20]:
        name = res.get("_id") or "Unknown"
        ldate = res.get("last_date")
        
        # Convert timestamp if it is string
        dt_obj = None
        if isinstance(ldate, str):
            try: dt_obj = datetime.fromisoformat(ldate.replace('Z', '+00:00'))
            except: pass
        elif isinstance(ldate, datetime):
            dt_obj = ldate
            
        status = "SILENT"
        if dt_obj and dt_obj > last_hour:
            status = "ACTIVE (Last 1h)"
            active_count += 1
        
        print(f"Group: {str(name)[:30]:<30} | Msgs: {res['total_msgs']:<5} | Last: {ldate} | {status}")

    # Special check for user: 5 samples from random groups
    print("\n--- SAMPLE CHECK: Last 5 messages from any group ---")
    samples = list(messages_col.find().sort("timestamp", -1).limit(5))
    for s in samples:
        print(f"Time: {s.get('timestamp')} | Group: {s.get('group_name')} | Content: {str(s.get('message_content',''))[:50]}...")

if __name__ == "__main__":
    analyze_groups()
