import sys
import os
import json

# Add current dir to path
sys.path.append(os.getcwd())

from text_gen_parser import TextGenParser

def test_pallet_logic():
    parser = TextGenParser()
    
    test_cases = [
        "İSTANBUL PENDİK - ANKARA MERKEZ 3 palet yük",
        "MERSİN - İZMİR 10 palet yük",
        "GAZİANTEP - DİYARBAKIR 7 palet",
        "ANTALYA - BURSA 8 palet"
    ]
    
    print("=== DYNAMIC PALLET CORRECTION TEST ===")
    for msg in test_cases:
        # Simulate the correction directly to avoid API calls for simple unit test
        route = {"yuk_tipi": ["KOMPLE"], "aciklama": msg}
        corrected = parser._apply_dynamic_pallet_correction(msg, route)
        
        print(f"\nMessage: {msg}")
        print(f"  Final Yük Tipi: {corrected['yuk_tipi']}")
        print(f"  Note: {corrected['aciklama'].split(']')[0] + ']' if '[' in corrected['aciklama'] else 'No change'}")

if __name__ == "__main__":
    test_pallet_logic()
