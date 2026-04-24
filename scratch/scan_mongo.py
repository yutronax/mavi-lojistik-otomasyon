
import os
from pymongo import MongoClient
from dotenv import load_dotenv

def scan_db():
    load_dotenv()
    mongo_uri = os.getenv("MONGODB_URI")
    client = MongoClient(mongo_uri)
    
    print("Listing all Databases:")
    for db_name in client.list_database_names():
        print(f" - {db_name}")
        db = client[db_name]
        print(f"   Collections in {db_name}: {db.list_collection_names()}")

if __name__ == "__main__":
    scan_db()
