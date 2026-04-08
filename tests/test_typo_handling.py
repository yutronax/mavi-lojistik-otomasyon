import logging
import sys
import os
import re

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

# Force disable simulation and setup API Key
os.environ['SIMULATED_GEMINI'] = '0'
if not os.getenv('GEMINI_API_KEY') and os.getenv('GEMINI_API_KEYS'):
    # Pick the first key
    os.environ['GEMINI_API_KEY'] = os.getenv('GEMINI_API_KEYS').split(',')[0].strip()

from src.parsers.group_based_parser import GroupBasedParser



# Setup logging
logging.basicConfig(
    filename='typo_debug.log',
    filemode='w',
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)


def test_typo_correction():
    config = {
        "parser_type": "openai",
        "model": "gemini-2.0-flash-exp",
        "temperature": 0.1,
        "message_defaults": {
            "arac_tipi": ["1360"],
            "kasa_tipi": ["KAPALI"],
            "yuk_tipi": ["KOMPLE"]
        }
    }
    
    parser = GroupBasedParser(config)
    
    with open("test_results.txt", "w", encoding="utf-8") as f:
        # Test 1: Typos in City/District
        msg_typo = """
        Istnbul - Ankr
        Gybze - Izmirr
        Adana Ceyhn - Mersin Merkz
        """
        
        f.write("\n--- TEST 1: Typos ---\n")
        try:
            results = parser.parse_with_openai(msg_typo, "test_typo", config)
            for r in results:
                f.write(f"Route: {r['nereden_il']}/{r['nereden_ilce']} -> {r['nereye_il']}/{r['nereye_ilce']}\n")
        except Exception as e:
            f.write(f"Error: {e}\n")

        # Test 2: Types Explicit vs Default
        # "biri açık diğeri varsayılan" senaryosu
        msg_types = """
        ISTANBUL - ANKARA AÇIK
        KOCAELI - IZMIR
        """
        
        f.write("\n--- TEST 2: Type Inference ---\n")
        try:
            results = parser.parse_with_openai(msg_types, "test_types", config)
            for r in results:
                # Pretty print dict
                f.write(f"Route: {r['nereden_il']} -> {r['nereye_il']} | Type: {r.get('type')} | Internal: Arac={r['arac_tipi']} Kasa={r['kasa_tipi']}\n")
        except Exception as e:
            f.write(f"Error: {e}\n")


if __name__ == "__main__":
    test_typo_correction()
