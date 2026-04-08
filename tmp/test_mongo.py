import os
import sys
from dotenv import load_dotenv

# Root path ayarı
current_dir = os.path.dirname(os.path.abspath(__file__))
root_path = os.path.dirname(current_dir)
sys.path.insert(0, root_path)

from src.services.mongo_service import MongoDataService

def test_connection():
    try:
        load_dotenv()
        print(f"Checking MONGODB_URI...")
        if not os.getenv('MONGODB_URI'):
            print("ERROR: MONGODB_URI not found.")
            return

        service = MongoDataService()
        blacklist = service.load_blacklist()
        print(f"SUCCESS: Connected to MongoDB. Blacklist count: {len(blacklist)}")
        print(f"Blacklist samples: {blacklist[:5]}")
    except Exception as e:
        print(f"FAILURE: {e}")

if __name__ == "__main__":
    test_connection()
