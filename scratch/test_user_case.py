import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

def test_screenshot_cases():
    parser = TextGenParser()
    
    messages = [
        "SABAH TOPKAPI YÜKLER- KÜÇÜKÇEKMECE TENTELİ TIR",
        "SABAH SİLİVRİ YÜKLER - BURSA KEMALPAŞA TIRA PARÇA 7.5 METRE YER"
    ]
    
    print("="*60)
    print("SCREENSHOT CASE TESTING")
    print("="*60)
    
    for msg in messages:
        print(f"\nMessage: {msg}")
        # We need to capture the raw response to see akil_yurutme
        # TextGenParser.parse normally returns list of routes
        # I'll call the primary model logic manually or check how it processes
        
        routes = parser.parse(msg)
        print(f"Result: {len(routes)} routes")
        for i, r in enumerate(routes):
            print(f"  Route {i+1}: {r.get('nereden_il')} {r.get('nereden_ilce')} -> {r.get('nereye_il')} {r.get('nereye_ilce')}")

if __name__ == "__main__":
    test_screenshot_cases()
