
import json
import os
import sys

# Data provided by user
updates_csv = """
ADANA,ÇUKUROVA
ANKARA,YENİMAHALLE
ANTALYA,KONYAALTI
AYDIN,EFELER
BALIKESİR,KARESİ
BURSA,NİLÜFER
DENİZLİ,MERKEZEFENDİ
DİYARBAKIR,SUR
ERZURUM,AZİZİYE
ESKİŞEHİR,ODUNPAZARI
GAZİANTEP,ŞEHİTKAMİL
HATAY,ANTAKYA
İZMİR,BORNOVA
KAHRAMANMARAŞ,ONİKİŞUBAT
KAYSERİ,KOCASİNAN
MALATYA,BATTALGAZİ
MANİSA,ŞEHZADELER
MARDİN,ARTUKLU
MERSİN,AKDENİZ
MUĞLA,ORTACA
ORDU,ALTINORDU
SAKARYA,ADAPAZARI
SAMSUN,İLKADIM
ŞANLIURFA,EYYÜBİYE
TEKİRDAĞ,SÜLEYMANPAŞA
TRABZON,ORTAHİSAR
VAN,İPEKYOLU
"""

# Istanbul sides handled in code, skipped here.
# Note: User wrote MOĞLA -> I corrected to MUĞLA.

def update_json():
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(base_dir, 'data', 'il_ilçeler.json')
    
    print(f"Reading {json_path}...")
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Parse updates
    update_map = {}
    for line in updates_csv.strip().split('\n'):
        if ',' in line:
            city, dist = line.split(',')
            update_map[city.strip()] = dist.strip().title() # Title case for JSON consistency if needed, but strict check is diff.
            # Actually, let's keep user casing or Upper? JSON seems to have Mixed/Title usually.
            # Checked file: "Adana", "Seyhan". So Title case is good.
    
    # Manual casing fixes for Turkish chars if simple .title() fails (e.g. İ -> i issue)
    # Actually, simpler to just start with Title and fix specifics if needed.
    # But better: Use the casing provided by user but title-cased properly.
    
    # Apply updates
    updates_count = 0
    for entry in data:
        normalized_il = entry['il'].replace('İ', 'I').upper() # Simple approximation for matching
        # Better: just check equality directly
        il_upper = entry['il'].upper().replace('İ','I') # Rough check
        
        # Let's match by exact string if possible, or normalized
        target_city = None
        for k in update_map.keys():
            # Handle I/İ confusion
            k_norm = k.replace('İ','I').upper()
            e_norm = entry['il'].replace('İ','I').upper()
            if k_norm == e_norm:
                target_city = k
                break
        
        if target_city:
            new_default = update_map[target_city]
            # Fix casing of new_default to match existing district list if possible
            # Find the district in the list to get proper casing
            proper_casing = new_default
            for d in entry.get('ilçe', []):
                if d.upper().replace('İ','I') == new_default.upper().replace('İ','I'):
                    proper_casing = d
                    break
            
            old_default = entry.get('varsayılan_ilçe', 'None')
            if old_default != proper_casing:
                entry['varsayılan_ilçe'] = proper_casing
                try:
                    print(f"Updated {entry['il']}: {old_default} -> {proper_casing}")
                except UnicodeEncodeError:
                    print(f"Updated {entry['il']} (Unicode Error in print)")
                updates_count += 1
            else:
                try:
                    print(f"Skipped {entry['il']}: Already {proper_casing}")
                except UnicodeEncodeError:
                    print(f"Skipped {entry['il']} (Unicode Error in print)")

    if updates_count > 0:
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"\nSaved {updates_count} updates to JSON.")
    else:
        print("\nNo changes needed.")

if __name__ == "__main__":
    # Force UTF-8 output if possible
    if sys.stdout.encoding.lower() != 'utf-8':
        try:
           sys.stdout.reconfigure(encoding='utf-8')
        except:
           pass
    update_json()
