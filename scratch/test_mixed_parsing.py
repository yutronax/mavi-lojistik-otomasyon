import os
import sys
import json

# Add src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from production_parser import ProductionParser

def test_mixed_message():
    parser = ProductionParser()
    message = """ANKARA ISTANBUL TIR 0532 123 45 67
ANKARA IZMIR 6 METRE TIR 0532 123 45 67"""
    
    print(f"Karma mesaj test ediliyor:\n{message}\n")
    results = parser.parse_message(message)
    
    for i, r in enumerate(results, 1):
        print(f"Rota {i}: {r['nereden_il']} -> {r['nereye_il']}")
        print(f"Yük Tipi: {r['yuk_tipi']}")
        print("-" * 20)

if __name__ == "__main__":
    test_mixed_message()
