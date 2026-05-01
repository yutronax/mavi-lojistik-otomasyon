import os
import sys
import json

# Add src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from production_parser import ProductionParser

def test_complex_scenarios():
    parser = ProductionParser()
    
    # Çok daha karmaşık, gerçekçi bir WhatsApp mesajı örneği
    message = """SELAMUN ALEYKUM HAYIRLI ISLER. ADANA SARIHAMZALI DAN YUKLEYIP ISTANBUL AVRUPA YAKASINA GIDECEK 13.60 TIR BRANDALI KOMPLE YUKUMUZ VARDIR. ACIL.
AYRICA AYNI YERDEN KOCAELI GEBZE TARAFINA 4 METRE YER KAPLAYAN 3 PALETLIK PARCA ESYAMIZ MEVCUTTUR.
BIR DE BURSA INEGOL - ANKARA ARASI CALISACAK KIRKAYAK VEYA ON TEKER ACIK KASA ARAC ARANIYOR.
ILGILENENLER: 0532 999 88 77 - MEHMET BEY"""
    
    print(f"Karmaşık Test Mesajı:\n{message}\n")
    results = parser.parse_message(message)
    
    print("=" * 50)
    print("AYRIŞTIRMA SONUÇLARI")
    print("=" * 50)
    
    for i, r in enumerate(results, 1):
        print(f"İlan {i}:")
        print(f"  Rota: {r['nereden_il']}/{r['nereden_ilce']} -> {r['nereye_il']}/{r['nereye_ilce']}")
        print(f"  Araç: {r['arac_tipi']}")
        print(f"  Yük Tipi: {r['yuk_tipi']}")
        print(f"  Kasa: {r['kasa_tipi']}")
        print("-" * 30)

if __name__ == "__main__":
    test_complex_scenarios()
