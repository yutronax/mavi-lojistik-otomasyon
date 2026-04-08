
import json
import os
import datetime

print("--- Data File Timestamp Check (Dynamic Path) ---")

# Find the 'data' directory dynamically to avoid encoding issues
current_dir = os.getcwd()
data_dir = os.path.join(current_dir, 'data')

if not os.path.exists(data_dir):
    print(f"Data directory not found at: {data_dir}")
    # Try alternate encoding or listing
    print("Listing current directory:")
    for entry in os.scandir(current_dir):
        print(f" - {entry.name}")
else:
    files_to_check = {
        'live_messages.json': 'Live Messages',
        'onaylanmamis_ayristirilmis.json': 'Unprocessed',
        'onaylanan_kayitlar.json': 'Processed'
    }
    
    for filename, display_name in files_to_check.items():
        fpath = os.path.join(data_dir, filename)
        
        if not os.path.exists(fpath):
            print(f"{display_name}: File not found ({filename})")
            continue
            
        try:
            with open(fpath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                
            timestamps = []
            if isinstance(data, list):
                for item in data:
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
                print(f"{display_name}: {len(data)} items, Latest: {dt}")
            else:
                print(f"{display_name}: {len(data) if isinstance(data, list) else 0} items, No timestamps found")
                
        except Exception as e:
            print(f"{display_name}: Error reading - {e}")
