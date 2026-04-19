import os
import sys

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timezone
import pymongo
from pymongo import MongoClient

# Add root directory to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from src.utils.config import load_config

load_config()

# Setup MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGODB_URI)
db = client["mavi_lojistik"]
collection = db["raw_group_data"]

# Consumer local state tracking
TRACKER_FILE = os.path.join(ROOT_DIR, "last_read_time.txt")

def get_last_read_time() -> datetime:
    """Retrieve the last read time. If none exists, default to epoch 0."""
    try:
        if os.path.exists(TRACKER_FILE):
            with open(TRACKER_FILE, "r") as f:
                ts = float(f.read().strip())
                return datetime.fromtimestamp(ts, tz=timezone.utc)
    except Exception as e:
        print(f"[!] Error reading tracker file: {e}")
        
    return datetime.fromtimestamp(0, tz=timezone.utc)

def set_last_read_time(dt: datetime):
    """Store the last read time locally."""
    try:
        with open(TRACKER_FILE, "w") as f:
            f.write(str(dt.timestamp()))
    except Exception as e:
        print(f"[ERR] Error writing tracker file: {e}")

class RawDataConsumer:
    """
    Consumer node behavior:
    1. Connect read-only
    2. Query ingested_at > last_read_time
    3. Retrieve raw_blob
    4. Store last_read_time locally
    """
    def __init__(self):
        self.collection = collection
        self.last_read = get_last_read_time()

    def process_new_blobs(self):
        """Fetches raw blobs newer than last_read_time and physically writes them to /data/."""
        query = {
            "ingested_at": {
                "$gt": self.last_read
            }
        }
        
        # Sort by ingested_at ascending to process oldest first
        cursor = self.collection.find(query).sort("ingested_at", pymongo.ASCENDING)
        
        fetched_count = 0
        latest_time = self.last_read
        data_dir = os.path.join(ROOT_DIR, "data")
        
        for doc in cursor:
            file_name = doc.get("file_name")
            raw_blob = doc.get("raw_blob")
            ingested_at = doc.get("ingested_at")
            
            # Pymongo returns naive UTC datetimes, we need it offset-aware to compare
            if ingested_at and ingested_at.tzinfo is None:
                ingested_at = ingested_at.replace(tzinfo=timezone.utc)
            
            if file_name and raw_blob:
                local_path = os.path.join(data_dir, file_name)
                
                # Check if file already exists locally to prevent unnecessary I/O bounds
                if not os.path.exists(local_path):
                    try:
                        with open(local_path, "wb") as f:
                            f.write(raw_blob)
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] [IN] Synced from Cloud: {file_name}")
                    except Exception as e:
                        print(f"[ERR] Failed to write {file_name} locally: {e}")
                
            # Track the latest time seen
            if ingested_at > latest_time:
                latest_time = ingested_at
                
            fetched_count += 1
            
        # Update local tracker if we processed new records
        if fetched_count > 0:
            set_last_read_time(latest_time)
            self.last_read = latest_time
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] Caught up to cloud state ({latest_time})")

def start_consumer_loop():
    print("[START] Starting MongoDB Cloud Sync Consumer...")
    print(f"[DIR] Target directory: {os.path.join(ROOT_DIR, 'data')}")
    
    consumer = RawDataConsumer()
    import time
    
    try:
        while True:
            consumer.process_new_blobs()
            time.sleep(3) # Poll every 3 seconds for near-real-time sync
    except KeyboardInterrupt:
        print("\n[STOP] Shutting down consumer node.")

if __name__ == "__main__":
    start_consumer_loop()
