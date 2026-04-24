
import json
import os

def check_live_struct():
    with open("data/live_messages.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if data and len(data) > 0:
        print("Sample Live Message Structure:")
        for k, v in data[0].items():
            print(f" - {k}: {type(v)} | Sample: {str(v)[:50]}")

if __name__ == "__main__":
    check_live_struct()
