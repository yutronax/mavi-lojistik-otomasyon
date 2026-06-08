import logging
import sys
import os

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.parsers.group_based_parser import GroupBasedParser

# Setup basic logging to FILE to avoid console encoding issues
logging.basicConfig(
    filename='parser_test.log',
    filemode='w',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


def test_parser():
    # Mock config
    config = {
        "parser_type": "openai",
        "model": "gemini-2.0-flash-exp",
        "temperature": 0.1,
        "message_defaults": {
            "arac_tipi": ["1360"],
            "kasa_tipi": ["AÇIK", "KAPALI"],
            "yuk_tipi": ["KOMPLE"]
        }
    }
    
    parser = GroupBasedParser(config)
    
    import traceback
    try:
        # Test Message 1: Normal
        msg1 = """
        İSTANBUL ÇIKIŞLI
        ANKARA TESLİM
        13.60 AÇIK DORSE
        FİYAT: 25.000 TL + KDV
        0532 123 45 67
        """
        
        print("\n--- TEST 1: Normal ---")
        results1 = parser.parse_with_openai(msg1, "msg1", config)
        for r in results1:
            print(r)
            
        # Test Message 2: Short / Needs Default
        msg2 = """
        KOCAELİ - İZMİR
        BOŞ ARAÇ
        """
        print("\n--- TEST 2: Short ---")
        results2 = parser.parse_with_openai(msg2, "msg2", config)
        for r in results2:
            print(r)

        # Test Message 3: Multiple Routes & Regex
        msg3 = """
        ADANA CEYHAN'DAN
        MERSİN MERKEZ'E
        DÖKME YÜK
        
        GAZİANTEP - KİLİS
        10 TEKER ARAC
        
        0555 999 88 77
        1500 USD
        """
        print("\n--- TEST 3: Multiple ---")
        results3 = parser.parse_with_openai(msg3, "msg3", config)
        for r in results3:
            print(r)

    except Exception as e:
        with open("debug.log", "w") as f:
            f.write(traceback.format_exc())
        print("ERROR logged to debug.log")


if __name__ == "__main__":
    test_parser()
