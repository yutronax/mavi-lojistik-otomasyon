#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Cleans neighborhood names in il_ilçe_mahalle.json:
1. Remove suffixes: Mah, Mah., Köy, Köyü, Mahallesi, Beldesi
2. Extract parenthesized content as separate entries (without parens)
3. Example: "Gedik Tavukçuluk Mah (aydınlı Köyü)" -> ["Gedik Tavukçuluk", "aydınlı"]
"""

import json
import os
import re

def clean_name(raw_name):
    """
    Cleans a single neighborhood name.
    Returns a list of cleaned names (may be >1 if parentheses exist).
    """
    raw_name = raw_name.strip()
    if not raw_name:
        return []
    
    results = []
    
    # 1. Extract parenthesized part first
    paren_match = re.search(r'\(([^)]+)\)', raw_name)
    paren_content = None
    if paren_match:
        paren_content = paren_match.group(1).strip()
        # Remove the parenthesized part from main name
        main_part = raw_name[:paren_match.start()].strip()
    else:
        main_part = raw_name
    
    # 2. Clean the main part - remove suffixes
    main_clean = remove_suffixes(main_part)
    if main_clean:
        results.append(main_clean)
    
    # 3. Clean the parenthesized part (if any) - also remove suffixes
    if paren_content:
        paren_clean = remove_suffixes(paren_content)
        if paren_clean and paren_clean not in results:
            results.append(paren_clean)
    
    return results

def remove_suffixes(name):
    """Remove Mah, Mah., Köy, Köyü, Mahallesi, Beldesi etc. from end of name."""
    name = name.strip()
    if not name:
        return ""
    
    # Order matters - check longer suffixes first
    suffixes = [
        " Mahallesi", " mahallesi",
        " Beldesi", " beldesi",
        " Köyü", " köyü", " Koyu", " koyu",
        " Köy", " köy", " Koy", " koy",
        " Mah.", " mah.",
        " Mah", " mah",
        " MAH.", " MAH",
    ]
    
    for suffix in suffixes:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
            break
    
    return name.strip()

def process_file(input_path, output_path):
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    total_before = 0
    total_after = 0
    
    for il_entry in data:
        for ilce_entry in il_entry.get('ilceler', []):
            old_neighborhoods = ilce_entry.get('mahalleler', [])
            total_before += len(old_neighborhoods)
            
            new_neighborhoods = []
            seen = set()
            
            for raw_name in old_neighborhoods:
                cleaned_names = clean_name(raw_name)
                for cn in cleaned_names:
                    cn_lower = cn.lower()
                    if cn_lower not in seen and cn:
                        seen.add(cn_lower)
                        new_neighborhoods.append(cn)
            
            ilce_entry['mahalleler'] = new_neighborhoods
            total_after += len(new_neighborhoods)
    
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    print(f"Cleaning complete!")
    print(f"  Before: {total_before} neighborhoods")
    print(f"  After:  {total_after} neighborhoods")
    print(f"  Delta:  {total_after - total_before:+d}")
    print(f"  Output: {output_path}")
    print(f"  Size:   {os.path.getsize(output_path) / 1024:.1f} KB")

if __name__ == "__main__":
    target = os.path.join(os.getcwd(), "data", "il_ilçe_mahalle.json")
    process_file(target, target)
