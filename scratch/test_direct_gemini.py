import os
import asyncio
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

async def test_direct_gemini():
    api_key = os.getenv("GEMINI_API_KEY")
    print(f"API KEY: {api_key[:10]}...")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
    print("Sending request...")
    try:
        response = await model.generate_content_async("Hi, output 'OK' if you see this.")
        print(f"RESPONSE: {response.text}")
        print(f"USAGE: {response.usage_metadata}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(test_direct_gemini())
