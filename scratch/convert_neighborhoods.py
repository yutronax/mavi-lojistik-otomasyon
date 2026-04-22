#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Converts the GitHub turkey-neighbourhoods dataset (by city code)
into the project's il_ilçe_mahalle.json format.

Source format:  { "01": { "District": ["Mah1", "Mah2", ...] }, ... }
Target format:  [ { "il": "ADANA", "ilceler": [ { "ilce": "Ceyhan", "mahalleler": [...] } ] } ]
"""

import json
import os
import sys

# Plaka kodu -> İl adı eşlemesi (81 il)
PLAKA_TO_IL = {
    "01": "ADANA", "02": "ADIYAMAN", "03": "AFYONKARAHİSAR", "04": "AĞRI",
    "05": "AMASYA", "06": "ANKARA", "07": "ANTALYA", "08": "ARTVİN",
    "09": "AYDIN", "10": "BALIKESİR", "11": "BİLECİK", "12": "BİNGÖL",
    "13": "BİTLİS", "14": "BOLU", "15": "BURDUR", "16": "BURSA",
    "17": "ÇANAKKALE", "18": "ÇANKIRI", "19": "ÇORUM", "20": "DENİZLİ",
    "21": "DİYARBAKIR", "22": "EDİRNE", "23": "ELAZIĞ", "24": "ERZİNCAN",
    "25": "ERZURUM", "26": "ESKİŞEHİR", "27": "GAZİANTEP", "28": "GİRESUN",
    "29": "GÜMÜŞHANE", "30": "HAKKARİ", "31": "HATAY", "32": "ISPARTA",
    "33": "MERSİN", "34": "İSTANBUL", "35": "İZMİR", "36": "KARS",
    "37": "KASTAMONU", "38": "KAYSERİ", "39": "KIRKLARELİ", "40": "KIRŞEHİR",
    "41": "KOCAELİ", "42": "KONYA", "43": "KÜTAHYA", "44": "MALATYA",
    "45": "MANİSA", "46": "KAHRAMANMARAŞ", "47": "MARDİN", "48": "MUĞLA",
    "49": "MUŞ", "50": "NEVŞEHİR", "51": "NİĞDE", "52": "ORDU",
    "53": "RİZE", "54": "SAKARYA", "55": "SAMSUN", "56": "SİİRT",
    "57": "SİNOP", "58": "SİVAS", "59": "TEKİRDAĞ", "60": "TOKAT",
    "61": "TRABZON", "62": "TUNCELİ", "63": "ŞANLIURFA", "64": "UŞAK",
    "65": "VAN", "66": "YOZGAT", "67": "ZONGULDAK", "68": "AKSARAY",
    "69": "BAYBURT", "70": "KARAMAN", "71": "KIRIKKALE", "72": "BATMAN",
    "73": "ŞIRNAK", "74": "BARTIN", "75": "ARDAHAN", "76": "IĞDIR",
    "77": "YALOVA", "78": "KARABÜK", "79": "KİLİS", "80": "OSMANİYE",
    "81": "DÜZCE"
}

def clean_neighborhood_name(name):
    """Remove 'Mah' suffix and clean whitespace."""
    name = name.strip()
    # Remove trailing "Mah" or "Mah." (case insensitive)
    if name.lower().endswith(" mah"):
        name = name[:-4].strip()
    elif name.lower().endswith(" mah."):
        name = name[:-5].strip()
    return name

def convert(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        source_data = json.load(f)
    
    result = []
    total_districts = 0
    total_neighborhoods = 0
    
    # Sort by plaka code for consistent output
    for code in sorted(source_data.keys(), key=lambda x: int(x)):
        il_name = PLAKA_TO_IL.get(code)
        if not il_name:
            print(f"WARNING: Unknown plaka code: {code}")
            continue
        
        districts_data = source_data[code]
        ilceler = []
        
        for district_name, neighborhoods in sorted(districts_data.items()):
            cleaned_neighborhoods = []
            for n in neighborhoods:
                clean_name = clean_neighborhood_name(n)
                if clean_name:
                    cleaned_neighborhoods.append(clean_name)
            
            ilceler.append({
                "ilce": district_name,
                "mahalleler": cleaned_neighborhoods
            })
            total_districts += 1
            total_neighborhoods += len(cleaned_neighborhoods)
        
        result.append({
            "il": il_name,
            "ilceler": ilceler
        })
    
    # Write output
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    
    print(f"Conversion complete!")
    print(f"  Cities: {len(result)}")
    print(f"  Districts: {total_districts}")
    print(f"  Neighborhoods: {total_neighborhoods}")
    print(f"  Output: {output_path}")
    print(f"  Size: {os.path.getsize(output_path) / 1024:.1f} KB")

if __name__ == "__main__":
    # Read the raw content from the downloaded file
    raw_path = r"C:\Users\YUSUF ÇİNAR\.gemini\antigravity\brain\7084cb00-d49a-4332-b9b4-6cf713b27a10\.system_generated\steps\224\content.md"
    
    # Extract JSON from the markdown wrapper
    with open(raw_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Find the JSON start (after the markdown header)
    json_start = content.index('{')
    json_content = content[json_start:]
    
    # Save clean JSON temporarily
    temp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_neighborhoods.json")
    with open(temp_path, 'w', encoding='utf-8') as f:
        f.write(json_content)
    
    # Convert
    output_path = os.path.join(os.getcwd(), "data", "il_ilçe_mahalle.json")
    
    # Backup existing file
    if os.path.exists(output_path):
        backup_path = output_path + ".old_backup"
        import shutil
        shutil.copy2(output_path, backup_path)
        print(f"Backed up existing file to: {backup_path}")
    
    convert(temp_path, output_path)
    
    # Cleanup temp
    os.remove(temp_path)
