import os
import sys
import json
from dotenv import load_dotenv

# Project root'u ekle
sys.path.insert(0, r"c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik")

# text_gen_parser'ın bulunduğu dizini ekle
sys.path.append(r"c:\Users\YUSUF ÇİNAR\OneDrive\Belgeler\Masaüstü\projelerim\maviLojistik")

from text_gen_parser import TextGenParser

def test_seramik():
    parser = TextGenParser()
    
    # User'ın belirttiği sorunu simüle edelim
    test_message = "İZMİR ANKARA SERAMİK 13.60"
    
    print("="*50)
    print(f"TEST MESAJI: {test_message}")
    print("="*50)
    
    # TextGenParser'ın ham çıktısını görmek için parse metodunu izleyebiliriz
    # Veya direkt çalıştırıp sonucu görebiliriz
    results = parser.parse(test_message)
    
    print("\nPARSED RESULTS:")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    
    if results:
        r = results[0]
        print(f"\nExtracted Load Type: {r.get('yuk_tipi')}")
        print(f"Extracted Vehicle Type: {r.get('arac_tipi')}")
        print(f"Extracted Body Type: {r.get('kasa_tipi')}")

if __name__ == "__main__":
    load_dotenv()
    test_seramik()
