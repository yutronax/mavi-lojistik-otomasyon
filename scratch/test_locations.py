import sys
import os
import json

# Add current directory to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

def test_locations():
    parser = TextGenParser()
    
    test_cases = [
        {
            "name": "Rize Confusion Test (Rize vs Vize)",
            "msg": "Rize yükleme Esenyurt kapalı tır 05321112233",
            "expected_origin": ("RİZE", "MERKEZ")
        },
        {
            "name": "Mersin Confusion Test (Mersin vs Meriç)",
            "msg": "Mersin çıkışlı İstanbul Başakşehir tır lazım",
            "expected_origin": ("MERSİN", "MERKEZ")
        },
        {
            "name": "Neighborhood Test (Hadımköy)",
            "msg": "Hadımköy - Ankara 1360 tır",
            "expected_origin": ("İSTANBUL", "ARNAVUTKÖY") # Hadımköy is usually associated with Arnavutköy
        },
        {
            "name": "Neighborhood Test (İkitelli)",
            "msg": "İkitelli yükleme Gebze tır",
            "expected_origin": ("İSTANBUL", "BAŞAKŞEHİR") # İkitelli is in Başakşehir
        }
    ]

    print("="*60)
    print("LOCATION RESOLUTION TEST RESULTS")
    print("="*60)
    
    all_passed = True
    for case in test_cases:
        print(f"\nTest: {case['name']}")
        print(f"Message: {case['msg']}")
        
        results = parser.parse(case['msg'])
        
        if not results:
            print("❌ FAILURE: No routes parsed.")
            all_passed = False
            continue
            
        r = results[0]
        actual_origin = (r['nereden_il'], r['nereden_ilce'])
        
        print(f"Actual: {actual_origin[0]} / {actual_origin[1]}")
        print(f"Expect: {case['expected_origin'][0]} / {case['expected_origin'][1]}")
        
        # Check if actual city matches expected city (priority)
        if actual_origin[0] == case['expected_origin'][0]:
             print("✅ City Match!")
        else:
             print("❌ City Mismatch!")
             all_passed = False
             
        # Check district (optional but good)
        if actual_origin[1] == case['expected_origin'][1]:
             print("✅ District Match!")
        else:
             print(f"⚠️ District Mismatch (Got {actual_origin[1]})")

    if all_passed:
        print("\n\n🎉 ALL LOCATION TESTS PASSED!")
    else:
        print("\n\n🛑 SOME TESTS FAILED. CHECK LOGS ABOVE.")

if __name__ == "__main__":
    test_locations()
