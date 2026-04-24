
import asyncio
import os
from google import genai
from dotenv import load_dotenv

async def check_all_keys():
    load_dotenv()
    keys_str = os.getenv('GEMINI_API_KEYS', '')
    keys = [k.strip() for k in keys_str.split(',') if k.strip()]
    
    print(f"Total {len(keys)} keys found. Scanning...\n")
    
    for i, k in enumerate(keys):
        masked = k[:6] + "..." + k[-4:]
        try:
            # Using synchronous call in a thread to keep it simple
            client = genai.Client(api_key=k)
            response = client.models.generate_content(
                model='gemini-2.0-flash',
                contents="test"
            )
            print(f"OK [{i+1}] {masked}: WORKING")
        except Exception as e:
            err = str(e)
            if "429" in err:
                print(f"LIMIT [{i+1}] {masked}: QUOTA EXCEEDED (429)")
            elif "400" in err:
                print(f"INVALID [{i+1}] {masked}: BAD REQUEST (400)")
            else:
                print(f"ERROR [{i+1}] {masked}: {err[:50]}...")

if __name__ == "__main__":
    asyncio.run(check_all_keys())
