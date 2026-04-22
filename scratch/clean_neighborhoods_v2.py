#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Second pass cleanup: catches edge cases the first pass missed.
Handles: bitişik köyü/köy, Köy at end after space, etc.
"""

import json
import os
import re

def deep_clean(name):
    """Deep clean a single neighborhood name - handles all edge cases."""
    name = name.strip()
    if not name:
        return ""
    
    # Already handled in first pass, but double-check:
    # Remove " Mah", " Mah.", " Mahallesi" (case-insensitive at end)
    name = re.sub(r'\s+[Mm]ah\.?\s*$', '', name)
    name = re.sub(r'\s+[Mm]ahallesi\s*$', '', name)
    
    # Remove " Köyü", " Köy", " Beldesi" at end (with space before)
    name = re.sub(r'\s+[Kk]öyü\s*$', '', name)
    name = re.sub(r'\s+[Kk]öy\s*$', '', name)
    name = re.sub(r'\s+[Kk]oyu\s*$', '', name)  # ASCII variant
    name = re.sub(r'\s+[Kk]oy\s*$', '', name)
    name = re.sub(r'\s+[Bb]eldesi\s*$', '', name)
    
    # Handle bitişik: "Emirinköyü" -> "Emirin", "Hacıbeyköyü" -> "Hacıbey"
    # But be careful not to strip "köy" from names like "Köyceğiz"
    # Only strip if the word is at the actual END and preceded by valid chars
    name = re.sub(r'köyü$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'köy$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'koyu$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'koy$', '', name, flags=re.IGNORECASE)
    
    return name.strip()

def process_file(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total_cleaned = 0
    total_removed = 0
    
    for il_entry in data:
        for ilce_entry in il_entry.get('ilceler', []):
            old_neighborhoods = ilce_entry.get('mahalleler', [])
            new_neighborhoods = []
            seen = set()
            
            for name in old_neighborhoods:
                cleaned = deep_clean(name)
                if cleaned:
                    cl = cleaned.lower()
                    if cl not in seen:
                        seen.add(cl)
                        new_neighborhoods.append(cleaned)
                    else:
                        total_removed += 1
                else:
                    total_removed += 1
                
                if cleaned != name:
                    total_cleaned += 1
            
            ilce_entry['mahalleler'] = new_neighborhoods
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Deep clean complete!")
    print(f"  Names cleaned: {total_cleaned}")
    print(f"  Duplicates removed: {total_removed}")
    print(f"  Size: {os.path.getsize(output_path) / 1024:.1f} KB")

if __name__ == "__main__":
    target = os.path.join(os.getcwd(), "data", "il_ilçe_mahalle.json")
    process_file(target, target)
