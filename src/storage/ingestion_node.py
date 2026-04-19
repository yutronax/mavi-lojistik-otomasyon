import os
import sys
import time
import random
import hashlib
import threading

if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
from datetime import datetime, timezone

# Add root directory to sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from src.utils.config import load_config
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pymongo import MongoClient
import pymongo

load_config()

# Setup MongoDB
MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGODB_URI)
db = client["mavi_lojistik"]
collection = db["raw_group_data"]

# Ensure indexing for performance
collection.create_index("checksum_hash", unique=True)
collection.create_index("ingested_at")

DATA_DIR = os.path.join(ROOT_DIR, "data")
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

def delete_file_delayed(file_path: str):
    """Delay deletion: random(600s – 1800s)"""
    delay = random.randint(600, 1800)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [CLEAN] Scheduling deletion of {os.path.basename(file_path)} in {delay} seconds.")
    time.sleep(delay)
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [CLEAN] Deleted {os.path.basename(file_path)} after {delay}s delay.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERR] Failed to delete {os.path.basename(file_path)}: {e}")

def process_file(file_path: str):
    """
    Ingest node behavior:
    1. Wait random(2s - 9s)
    2. Read entire file as RAW
    3. Compute checksum_hash
    4. Insert if new
    """
    if not os.path.isfile(file_path):
        return
        
    file_name = os.path.basename(file_path)
    
    # Ignore hidden, temporary, and backup files
    if file_name.startswith('.') or file_name.endswith('.tmp') or file_name.endswith('.bak') or '.backup' in file_name:
        return
    
    # Wait random(2s - 9s) before ingestion
    delay = random.uniform(2.0, 9.0)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [WAIT] Detected {file_name}. Waiting {delay:.1f}s before ingestion...")
    time.sleep(delay)
    
    # Ensure file still exists after wait
    if not os.path.exists(file_path):
        return
        
    try:
        # Read entire file as RAW
        with open(file_path, "rb") as f:
            raw_blob = f.read()
            
        file_size = len(raw_blob)
        if file_size == 0:
            return
            
        # Compute checksum_hash
        checksum_hash = hashlib.sha256(raw_blob).hexdigest()
        
        # If hash already exists: skip ingestion
        if collection.find_one({"checksum_hash": checksum_hash}):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] [SKIP] Skipping {file_name} - Hash already exists.")
            # Still schedule for delayed deletion if we don't want to keep local shares
            threading.Thread(target=delete_file_delayed, args=(file_path,), daemon=True).start()
            return
            
        # Get creation time
        stat = os.stat(file_path)
        created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
        ingested_at = datetime.now(timezone.utc)
        
        # Insert document into MongoDB collection
        doc = {
            "file_name": file_name,
            "file_path": file_path,
            "raw_blob": raw_blob,
            "file_size": file_size,
            "created_at": created_at,
            "ingested_at": ingested_at,
            "checksum_hash": checksum_hash
        }
        
        collection.insert_one(doc)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] Ingested {file_name} ({file_size} bytes).")
        
        # Post-ingestion: schedule delayed local deletion
        threading.Thread(target=delete_file_delayed, args=(file_path,), daemon=True).start()
        
    except pymongo.errors.DuplicateKeyError:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [SKIP] Skipping {file_name} - Hash collided during insert.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [ERR] Error processing {file_name}: {e}")


class RawDataHandler(FileSystemEventHandler):
    def on_created(self, event):
        if not event.is_directory:
            threading.Thread(target=process_file, args=(event.src_path,), daemon=True).start()

    def on_modified(self, event):
        if not event.is_directory:
            threading.Thread(target=process_file, args=(event.src_path,), daemon=True).start()


def start_ingestion_node():
    print("[START] Starting MongoDB Ingestion Node...")
    print(f"📁 Watching directory: {DATA_DIR}")
    print(f"[NET] MongoDB URI: {MONGODB_URI}")
    
    event_handler = RawDataHandler()
    observer = Observer()
    observer.schedule(event_handler, DATA_DIR, recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\n[STOP] Shutting down ingestion node.")
    
    observer.join()

if __name__ == "__main__":
    start_ingestion_node()
