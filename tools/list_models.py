import os
import sys
from dotenv import load_dotenv
import google.generativeai as genai

# Fix Windows encoding
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

load_dotenv()

api_key = os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
if not api_key:
    print("❌ API Key not found in environment!")
    sys.exit(1)

genai.configure(api_key=api_key)

print(f"🔑 Checking models with API Key: {api_key[:5]}...{api_key[-5:]}")
print("-" * 50)

try:
    print("Fetching models...")
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ {m.name}")
except Exception as e:
    print(f"❌ Error listing models: {e}")
