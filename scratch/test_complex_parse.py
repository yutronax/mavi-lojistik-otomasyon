import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from text_gen_parser import TextGenParser

async def test_complex():
    parser = TextGenParser()
    
    # Seyir Lojistik Testi
    complex_message = """
    *!!! SABAH YÜKLER !!!*

    *Ankara Temelli - Eskişehir Parça*

    *Afyon Çay - Karaman TIR (Kapalı)*

    SEYİR LOJİSTİK

    0506 504 7087
    """
    
    print("\n--- TEST BASLIYOR ---")
    results = await parser.parse_async(complex_message)
    
    print(f"\n[3] BULUNAN ROTA SAYISI: {len(results)}")
    for i, r in enumerate(results, 1):
        print(f"\n--- ROTA #{i} ---")
        print(f"Cikis: {r.get('nereden_il')} / {r.get('nereden_ilce')}")
        print(f"Varis: {r.get('nereye_il')} / {r.get('nereye_ilce')}")
        print(f"Arac: {r.get('arac_tipi')} | Kasa: {r.get('kasa_tipi')}")
        print(f"Yuk: {r.get('yuk_tipi')} | Telefon: {r.get('telefon')}")

if __name__ == "__main__":
    asyncio.run(test_complex())
