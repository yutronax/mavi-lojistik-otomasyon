import json

def check_locs():
    with open('data/il_ilçe_mahalle.json', encoding='utf-8') as f:
        data = json.load(f)
        
    targets = ["SİTELER", "OVACIK", "VEZİRHAN", "AKYURT", "PURSAKLAR", "ÇUBUK"]
    found = {}
    
    for entry in data:
        il = entry['il']
        for ilce_obj in entry['ilceler']:
            ilce = ilce_obj['ilce']
            mahalleler = ilce_obj.get('mahalleler', [])
            
            # Check ilce name
            if ilce.upper() in targets:
                if ilce.upper() not in found: found[ilce.upper()] = []
                found[ilce.upper()].append(f"ILCE: {il}")
                
            # Check mahalleler
            for m in mahalleler:
                if m.upper() in targets:
                    if m.upper() not in found: found[m.upper()] = []
                    found[m.upper()].append(f"MAHALLE: {il}/{ilce}")
                    
    for t in targets:
        print(f"{t}: {found.get(t, 'NOT FOUND')}")

if __name__ == "__main__":
    check_locs()
