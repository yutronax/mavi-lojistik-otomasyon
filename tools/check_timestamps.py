
import json
import os
import datetime

# Use raw strings for paths to handle special characters
files = {
    'Live Messages': r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\data\live_messages.json',
    'Unprocessed': r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\data\onaylanmamis_ayristirilmis.json', 
    'Processed': r'c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik\data\onaylanan_kayitlar.json'
}

print("--- Data File Timestamp Check ---")
for name, fpath in files.items():
    if not os.path.exists(fpath):
        print(f"{name}: File not found ({fpath})")
        continue
        
    try:
        with open(fpath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        timestamps = []
        if isinstance(data, list):
            for item in data:
                # Check various timestamp fields
                ts = None
                if isinstance(item, dict):
                    ts = item.get('timestamp') or \
                         item.get('message_timestamp') or \
                         item.get('message_info', {}).get('timestamp')
                
                if ts:
                    try:
                        timestamps.append(float(ts))
                    except:
                        pass
        
        if timestamps:
            max_ts = max(timestamps)
            dt = datetime.datetime.fromtimestamp(max_ts)
            print(f"{name}: {len(data)} items, Latest: {dt}")
        else:
            print(f"{name}: {len(data)} items, No timestamps found")
            
    except Exception as e:
        print(f"{name}: Error reading - {e}")
