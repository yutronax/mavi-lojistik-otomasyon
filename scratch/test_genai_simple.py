import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def test_genai_simple():
    api_key = os.getenv("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    try:
        response = client.models.generate_content(
            model='gemini-2.0-flash',
            contents='Hi'
        )
        print(f"SUCCESS: {response.text}")
    except Exception as e:
        print(f"ERROR: {e}")

if __name__ == "__main__":
    test_genai_simple()
