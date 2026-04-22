import sys
import os
import json

# Add project root to path
sys.path.insert(0, os.getcwd())

from text_gen_parser import TextGenParser

def test_operators():
    parser = TextGenParser()
    
    test_cases = [
        {
            "name": "Multi-Destination Test",
            "message": "Kocaeli çıkışlı Bursa + Yalova tır lazım",
            "expected_count": 2
        },
        {
            "name": "Alternative Vehicle Test",
            "message": "İstanbul - Ankara Tır + Kırkayak",
            "expected_count": 1
        }
    ]
    
    print("="*60)
    print("OPERATOR (+) LOGIC TESTS")
    print("="*60)
    
    for case in test_cases:
        print(f"\nTest: {case['name']}")
        print(f"Message: {case['message']}")
        
        routes = parser.parse(case['message'])
        
        print(f"Parsed Routes: {len(routes)}")
        for i, r in enumerate(routes):
            print(f"  Route {i+1}: {r.get('nereden_il')} -> {r.get('nereye_il')} ({r.get('type')})")
            
        if len(routes) == case['expected_count']:
            print("✅ Passed!")
        else:
            print(f"❌ Failed! Expected {case['expected_count']} routes.")

if __name__ == "__main__":
    test_operators()
