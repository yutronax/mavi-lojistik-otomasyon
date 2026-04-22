import os
import sys
from dotenv import load_dotenv
from groq import Groq

# Load .env from root
load_dotenv('.env')

def test_keys():
    raw_keys = os.getenv('GROQ_API_KEYS', '')
    keys = [k.strip() for k in raw_keys.split(',') if k.strip()]
    
    if not keys:
        single_key = os.getenv('GROQ_API_KEY')
        if single_key:
            keys = [single_key]

    if not keys:
        print("HATA: Hiç Groq anahtarı bulunamadı!")
        return

    print(f"Toplam {len(keys)} anahtar test ediliyor...\n")

    for i, key in enumerate(keys, 1):
        print(f"[{i}] Anahtar: {key[:8]}...{key[-4:]}")
        try:
            client = Groq(api_key=key)
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=5
            )
            print("  SONUÇ: ÇALIŞIYOR ✅")
        except Exception as e:
            if "401" in str(e):
                print("  SONUÇ: GEÇERSİZ (401) ❌")
            elif "429" in str(e):
                print("  SONUÇ: HIZ SINIRI (429) ⚠️")
            else:
                print(f"  SONUÇ: HATA - {str(e)}")

if __name__ == "__main__":
    test_keys()
