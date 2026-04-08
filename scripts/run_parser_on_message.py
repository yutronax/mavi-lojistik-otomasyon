import os
import sys
import json
from pathlib import Path

# ensure repo root in path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Force simulated Gemini for deterministic output
os.environ['SIMULATED_GEMINI'] = '1'

from src.infrastructure.llm.gemini import GeminiLLM
from src.infrastructure.parsers.llm_parser import LLMParser

MSG_FILE = ROOT / 'mesajlar.json'
ARTIFACTS = ROOT / 'artifacts'
ARTIFACTS.mkdir(exist_ok=True)

with open(MSG_FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

# pick first message that has a non-empty body
messages = data.get('messages', [])
msg = None
for m in messages:
    if m and m.get('body') and m.get('body').strip():
        msg = m
        break

if not msg:
    print('No suitable message found in mesajlar.json')
    sys.exit(2)

message_id = msg.get('id')
message_body = msg.get('body')

llm = GeminiLLM()
parser = LLMParser(llm)

shipments = parser.parse(message_body, message_id)

out = {
    'message_id': message_id,
    'original': message_body,
    'parsed_shipments': [s.to_dict() for s in shipments]
}

out_path = ARTIFACTS / f'parsed_{message_id}.json'
with open(out_path, 'w', encoding='utf-8') as f:
    json.dump(out, f, ensure_ascii=False, indent=2)

print(json.dumps(out, ensure_ascii=False, indent=2))
print('\nWrote artifact to', out_path)
