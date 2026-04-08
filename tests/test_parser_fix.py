
from text_gen_parser import TextGenParser
import json

parser = TextGenParser()

test_msg = """KIZILTEPEDEN✅✅
MALATYAYA MISIR 🌽 
KISA DORSA  

ADANA KARATAŞ MISIR 🌽 
KISA DORSA ✅

CEYHAN MISIR 🌽 
KISA DORSA ✅

ADANA SUNAR MISIR 🌽 
ACIK ARAÇLAR ✅

KAYSERİYE MISIR 🌽.  KISA DORSA 

HEMEN YÜKLER 
İRTBAT EREN NAKLİYAT 🚚 
05458950371
05421140947"""

print("Test Mesajı:")
print(test_msg)
print("-" * 50)

results = parser.parse(test_msg)

print(f"\nSonuç ({len(results)} rota):")
for i, r in enumerate(results, 1):
    print(f"{i}. {r['nereden_il']}/{r['nereden_ilce']} -> {r['nereye_il']}/{r['nereye_ilce']}")
    print(f"   Yük: {r.get('yuk_tipi')} / {r.get('arac_tipi')}")
    print("-" * 20)

# Validation
kiziltepe_correct = all(r['nereden_ilce'] == 'KIZILTEPE' or r['nereden_il'] == 'MARDİN' for r in results)
routes_found = len(results) >= 5

if kiziltepe_correct and routes_found:
    print("\n✅ TEST BAŞARILI: Kızıltepe global header olarak algılandı!")
else:
    print("\n❌ TEST BAŞARISIZ: Hatalı ayrıştırma.")

