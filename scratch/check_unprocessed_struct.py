
import json
import os

def check_unprocessed_struct():
    with open("data/islenmemis_mesajlar.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if data and len(data) > 0:
        print("Sample Unprocessed Message Structure:")
        # Take a sample from the end
        msg = data[-1]
        for k, v in msg.items():
            print(f" - {k}: {type(v)} | Sample: {str(v)[:50]}")

if __name__ == "__main__":
    check_unprocessed_struct()
