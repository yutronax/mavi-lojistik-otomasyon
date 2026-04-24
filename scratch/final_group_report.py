
import os
import time
import re
from pymongo import MongoClient
from datetime import datetime, timedelta
from dotenv import load_dotenv

def clean_text(text):
    # Strip emojis and non-ascii characters for Windows console
    if not text: return ""
    return re.sub(r'[^\x00-\x7F]+', '?', text)

def generate_report():
    load_dotenv()
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["mavi_lojistik"]
    inbox = db["inbox"]
    
    print("Mavi Lojistik Group Activity Report (Cleaned Names)")
    print("-" * 50)
    
    now_ts = time.time()
    one_hour_ago_ts = now_ts - 3600
    
    pipeline = [
        {"$sort": {"message_timestamp": -1}},
        {"$group": {
            "_id": "$message_info.chat_name",
            "last_ts": {"$first": "$message_timestamp"},
            "count": {"$sum": 1},
            "recent_5_times": {"$push": "$message_timestamp"}
        }},
        {"$project": {
            "group_name": "$_id",
            "last_ts": 1,
            "count": 1,
            "recent_5": {"$slice": ["$recent_5_times", 5]}
        }},
        {"$sort": {"last_ts": -1}}
    ]
    
    results = list(inbox.aggregate(pipeline))
    
    total_groups = len(results)
    active_now = 0
    
    print(f"Total Unique Groups Detected: {total_groups}")
    print(f"Current Time: {datetime.fromtimestamp(now_ts)}")
    print("-" * 50)
    
    for res in results[:50]: # Show top 50
        name = res.get("group_name") or "Unknown"
        last_ts = res.get("last_ts") or 0
        
        status = "SILENT (>1h)"
        if last_ts > one_hour_ago_ts:
            status = "ACTIVE (Last 1h)"
            active_now += 1
            
        last_date = datetime.fromtimestamp(last_ts) if last_ts > 0 else "Never"
        samples = [datetime.fromtimestamp(t).strftime('%H:%M') for t in res.get("recent_5", [])]
        
        # Clean name for console
        clean_name = clean_text(name)
        
        print(f"Group: {clean_name[:25]:<25} | Msgs: {res['count']:<4} | Last: {last_date} | {status}")
        print(f"      Samples: {', '.join(samples)}")

    # Summary needs a separate loop to count all active
    full_active_count = sum(1 for r in results if (r.get("last_ts") or 0) > one_hour_ago_ts)

    print("-" * 50)
    print(f"SUMMARY:")
    print(f" - Total detected groups in DB: {total_groups}")
    print(f" - Active groups in the last 60 minutes: {full_active_count}")
    print(f" - Most recent message came at: {datetime.fromtimestamp(results[0]['last_ts']) if results else 'N/A'}")

if __name__ == "__main__":
    generate_report()
