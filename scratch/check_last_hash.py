import os
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()
uri = os.getenv('MONGODB_URI')
client = MongoClient(uri, serverSelectionTimeoutMS=5000)
db = client.get_database('mavi_lojistik')
hashes = db.get_collection('processed_hashes')

last_hash = hashes.find().sort("createdAt", -1).limit(1)
for h in last_hash:
    print(f"Last Processed Hash CreatedAt: {h.get('createdAt')}")
