
import json
import os
import datetime

print("--- Data File Timestamp Check (Root Path) ---")

files_to_check = {
    'live_messages.json': 'Live Messages',
    'onaylanmamis_ayristirilmis.json': 'Unprocessed',
    'onaylanan_kayitlar.json': 'Processed',
    'mesajlar.json': 'Raw Messages'
}

current_dir = os.getcwd()

for filename, display_name in files_to_check.items():
    fpath = os.path.join(current_dir, filename)
    
    if not os.path.exists(fpath):
        # Also try in data/ just in case mixed locations
        fpath_data = os.path.join(current_dir, 'data', filename)
        if os.path.exists(fpath_data):
            fpath = fpath_data
        else:
            print(f"{display_name}: File not found ({filename})")
            continue
            
    try:
        # Get filesystem modification time first
        mtime = os.path.getmtime(fpath)
        mtime_dt = datetime.datetime.fromtimestamp(mtime)
        print(f"{display_name} (File MTime): {mtime_dt}")

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
            print(f"{display_name} (Content): {len(data)} items, Latest: {dt}")
        else:
            print(f"{display_name} (Content): {len(data) if isinstance(data, list) else 0} items, No timestamps found")
            
    except Exception as e:
        print(f"{display_name}: Error reading - {e}")
