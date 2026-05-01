import sys
import os
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.parsers.production_parser import ProductionParser

def test():
    parser = ProductionParser()
    msg = """Manisa OSB Burhaniye Tırda Kamyonda 3 metre yer yeterli plt malzeme 6500 kilo parça kapalı Araçlar uygundur hemen sarılır 0542 336 61 45 

Not Malzeme pazartesi teslimli"""
    
    result = parser.parse_message(msg)
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test()
