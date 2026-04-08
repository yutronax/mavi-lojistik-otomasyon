
import os
import sys
import json
import time

sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

def run_test():
    parser = TextGenParser()
    
    # Test cases focusing on Neighborhoods that are often mistaken for districts or require lookup
    test_cases = [
        # --- PREVIOUS SUCCESSES ---
        {"desc": "[BASELINE] Ostim (No Context)", "msg": "Ostim çıkışlı nakliye."},
        
        # --- TYPOS & PHONETIC ---
        {"desc": "[TYPO] Ikiteli (Typo)", "msg": "Ikiteli - Gebze."},
        {"desc": "[TYPO] Guzelyali ( No Turkish Chars)", "msg": "Izmir Guzelyali."},
        
        # --- AMBIGUOUS / GENERIC ---
        {"desc": "[AMBIGUOUS] Yeniköy (No Context - Challenging)", "msg": "Yeniköy'den yük."},
        {"desc": "[AMBIGUOUS] Sanayi (Too Generic)", "msg": "Sanayi çıkışlı."},
        
        # --- SPECIFIC / OBSCURE ---
        {"desc": "[SPECIFIC] Dudullu (Istanbul Side Check)", "msg": "Dudullu depodan."},
        {"desc": "[SPECIFIC] Keresteciler (Industrial Zone)", "msg": "Keresteciler sitesi Ankara."},
        {"desc": "[SPECIFIC] Şaşmaz (Ankara Auto Industry)", "msg": "Şaşmaz'dan parça yük."},
        
        # --- CROSS-CONTEXT CONFLICT ---
        {"desc": "[CONFLICT] Konyaaltı (Antalya) inside Ankara context", "msg": "Ankara Konyaaltı yükü."},  # Should strictly fail or pick best guess (Antalya)
        
        # --- VILLAGE ---
        {"desc": "[VILLAGE] Akçalar (Bursa Village)", "msg": "Bursa Akçalar."},
    ]
    
    print("-" * 60)
    print("TESTING NEIGHBORHOOD RESOLUTION LOGIC")
    print("-" * 60)
    
    for case in test_cases:
        print(f"\n[TEST] {case['desc']}")
        print(f"[INPUT] {case['msg']}")
        try:
            # Add delay to avoid aggressive rate limits during test
            time.sleep(3) 
            
            start = time.time()
            result = parser.parse(case['msg'])
            duration = time.time() - start
            
            routes = result if isinstance(result, list) else []
            for r in routes:
                print(f"[RESULT] {r.get('nereden_il')}/{r.get('nereden_ilce')} -> {r.get('nereye_il')}/{r.get('nereye_ilce')}")
            
            print(f"[RAW JSON] {json.dumps(result, ensure_ascii=False)}")
            print(f"[TIME] {duration:.2f}s")
            
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    run_test()
