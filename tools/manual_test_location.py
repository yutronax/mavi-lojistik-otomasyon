
import os
import sys
import json

# Setup path to import src
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

def run_test():
    parser = TextGenParser()
    
    test_cases = [
        {
            "desc": "HIERARCHY 1: City + District",
            "msg": "Ankara Etimesgut'tan İstanbul'a yük var."
        },
        {
            "desc": "HIERARCHY 2: City Only (Default District Check)",
            "msg": "Ankara'dan İstanbul'a yük."
        },
        {
            "desc": "HIERARCHY 3: City + Neighborhood",
            "msg": "İstanbul Kozyatağı'ndan koli."
        },
        {
            "desc": "HIERARCHY 4: District Only (Infer City)",
            "msg": "Gebze Çayırova arası nakliye."
        },
        {
            "desc": "HIERARCHY 5: Neighborhood Only (Infer All)",
            "msg": "Ostim - İkitelli arası parça yük."
        },
        {
            "desc": "VEHICLE: KISA DORSE -> 860 DAMPERLİ",
            "msg": "Adana'dan Mersin'e KISA DORSE lazım."
        },
        {
            "desc": "VEHICLE: 6 TEKER -> 10 TEKER Fallback",
            "msg": "İzmir - Manisa arası 6 TEKER araç."
        }
    ]
    
    print("-" * 60)
    print("STARTING MANUAL LOGIC VERIFICATION")
    print("-" * 60)
    
    for case in test_cases:
        print(f"\n[TEST] {case['desc']}")
        print(f"[INPUT] {case['msg']}")
        try:
            import time
            time.sleep(5) # Avoid Rate Limit
            result = parser.parse(case['msg'])
            print(f"[OUTPUT] {json.dumps(result, ensure_ascii=False, indent=2)}")
        except Exception as e:
            print(f"[ERROR] {e}")

if __name__ == "__main__":
    run_test()
