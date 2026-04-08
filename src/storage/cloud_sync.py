import threading
import time
import os
import sys

# Windows UTF-8 console output fix for emojis
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')

# Setup root dir
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

from src.storage.ingestion_node import start_ingestion_node
from src.storage.consumer_node import start_consumer_loop

def run_bidirectional_sync():
    """Starts both the watcher (uploader) and the consumer (downloader) simultaneously."""
    print("====================================")
    print("🌍 MAVI LOJISTIK CLOUD SYNC ENGINE 🌍")
    print("====================================")
    print("Starting Peer-to-Peer file synchronization via MongoDB...")
    
    # Start ingestion node (runs an observer loop blocking the thread if not a daemon, 
    # but we can wrap it or start it on a separate background thread)
    ingestion_thread = threading.Thread(target=start_ingestion_node, daemon=True)
    ingestion_thread.start()
    
    # Put a small delay so logs print cleanly
    time.sleep(1)
    
    # Start the consumer loop on the main thread so we can capture KeyboardInterrupt
    try:
        start_consumer_loop()
    except KeyboardInterrupt:
        print("\n🛑 Cloud Sync Engine terminating gracefully.")
        sys.exit(0)

if __name__ == "__main__":
    run_bidirectional_sync()
