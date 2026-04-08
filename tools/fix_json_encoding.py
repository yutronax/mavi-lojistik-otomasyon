
import json
import os
import unicodedata

def fix_json():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'data', 'il_ilçeler.json')
    
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    count = 0
    for entry in data:
        # Fix varsayılan_ilçe
        if 'varsayılan_ilçe' in entry:
            original = entry['varsayılan_ilçe']
            # Normalize to composed form (NFC or NFKC)
            # NFKC will combine characters if possible
            fixed = unicodedata.normalize('NFKC', original)
            
            # Additional manual strip of combining dot if it persists on 'i'
            # (Sometimes normalization doesn't strip it if it was 'i'+dot which creates 'i' with 2 dots or just 'i'?)
            # Let's simple check: if 'i' is there, we don't need extra dot.
            if 'i\u0307' in fixed or 'İ\u0307' in fixed.upper(): # checking combinations
                 fixed = fixed.replace('\u0307', '')
            
            # Also strictly replace "i\u0307" -> "i" just in case
            fixed = fixed.replace('i\u0307', 'i')
            
            if fixed != original:
                entry['varsayılan_ilçe'] = fixed
                try:
                    print(f"Fixed {entry['il']}: {original} -> {fixed}")
                except:
                    print(f"Fixed {entry['il']} (Unicode char)")
                count += 1
                
    if count > 0:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"Fixed {count} entries.")
    else:
        print("No encoding issues found.")

if __name__ == "__main__":
    fix_json()
