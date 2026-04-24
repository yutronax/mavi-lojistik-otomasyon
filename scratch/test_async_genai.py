import os
import asyncio
from dotenv import load_dotenv
from google import genai

load_dotenv()

async def t():
    key = os.getenv('GEMINI_API_KEY')
    print(f"Len: {len(key)}, Key: {key[:5]}...{key[-5:]}")
    
    # Strip just in case there are hidden characters
    clean_key = key.strip()
    
    client = genai.Client(api_key=clean_key)
    try:
        res = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.0-flash',
            contents='Hi'
        )
        print(f"SUCCESS: {res.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(t())
