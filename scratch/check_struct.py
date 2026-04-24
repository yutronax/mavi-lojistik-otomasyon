
import os
from pymongo import MongoClient
from dotenv import load_dotenv

def check_structure():
    load_dotenv()
    client = MongoClient(os.getenv("MONGODB_URI"))
    db = client["mavi_lojistik"]
    inbox = db["inbox"]
    
    doc = inbox.find_one()
    print("Sample Document Structure:")
    for key, value in doc.items():
        print(f" - {key}: {type(value)}")
        if key == "metadata" and isinstance(value, dict):
            print("   Metadata Keys:", value.keys())

if __name__ == "__main__":
    check_structure()
