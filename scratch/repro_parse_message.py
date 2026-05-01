import os
import sys
import json

# Add src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from production_parser import ProductionParser

def test_single_message():
    parser = ProductionParser()
    message = "AYDIN MERKEZ ZİLE 4 TON 6 METRE AÇIK TIR OLACAK....0532 431 11 97....0532 059 54 60"
    
    print(f"Test ediliyor: {message}\n")
    results = parser.parse_message(message)
    
    print("Ayrıştırma Sonucu:")
    print(json.dumps(results, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_single_message()
