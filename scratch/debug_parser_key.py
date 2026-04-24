import sys
import os
import asyncio
from dotenv import load_dotenv

sys.path.insert(0, os.getcwd())
from text_gen_parser import TextGenParser

load_dotenv()

async def debug_key():
    parser = TextGenParser()
    key = os.getenv("GEMINI_API_KEY")
    print(f"Env Key: {key}")
    
    # Test client
    client = parser._get_gemini_client()
    print(f"Client API Key: {client._api_key if hasattr(client, '_api_key') else 'Unknown'}")
    
    try:
        # Use simple thread call like in parser
        res = await asyncio.to_thread(
            client.models.generate_content,
            model='gemini-2.0-flash',
            contents='Hi'
        )
        print(f"Success: {res.text}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(debug_key())
