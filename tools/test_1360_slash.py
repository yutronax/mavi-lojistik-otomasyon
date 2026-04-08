
import sys
import os

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from text_gen_parser import TextGenParser

def test_1360_slash():
    parser = TextGenParser()
    
    # User's failing example (exact reproduction attempt)
    message = "Ankara İstanbul 13/60"
    
    print(f"Testing message: '{message}'")
    results = parser.parse(message)
    
    for i, r in enumerate(results):
        print(f"\nResult {i+1}:")
        print(f"  Vehicle: {r['arac_tipi']}")
        
        if '1360' in r['arac_tipi']:
             print("SUCCESS: 13/60 recognized as 1360")
        elif '860' in r['arac_tipi']:
            print("FAILURE: 13/60 recognized as 860")
        else:
            print(f"FAILURE: Unexpected result: {r['arac_tipi']}")

if __name__ == "__main__":
    test_1360_slash()
