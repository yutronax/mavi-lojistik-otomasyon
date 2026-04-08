import config_api_key
from google import genai
import inspect

client = genai.Client()
print('CLIENT OK')
print('client attrs:', [a for a in dir(client) if not a.startswith('_')])
if hasattr(client, 'models'):
    print('models attrs:', [a for a in dir(client.models) if not a.startswith('_')])
else:
    print('no client.models')

if hasattr(client, 'generate'):
    print('has top-level generate')

for name in ('generate_content','generate','list','create'):
    if hasattr(getattr(client, 'models', client), name):
        obj = getattr(getattr(client, 'models', client), name)
        try:
            print(f"signature for {name}:", inspect.signature(obj))
        except Exception as e:
            print(f"cannot get signature for {name}: {e}")
