import os
import json
import logging
from pathlib import Path

# Ensure simulated Gemini for deterministic outputs
os.environ['SIMULATED_GEMINI'] = '1'

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]
import sys
# Ensure project root on sys.path so local imports like `src.*` work when running as a script
sys.path.insert(0, str(ROOT))

from src.parsers.group_based_parser import GroupBasedParser
msg_file = ROOT / 'mesajlar.json'

with open(msg_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

messages = data.get('messages', [])
count = min(5, len(messages))

parser = GroupBasedParser()

results = []
for i in range(count):
    msg = messages[i]
    logger.info('Running parse for message %s (%d/%d)', msg.get('id'), i+1, count)
    try:
        parsed = parser.parse_message(msg)
    except Exception as e:
        logger.exception('Parser raised exception for message %s', msg.get('id'))
        parsed = {'error': str(e)}
    results.append({'id': msg.get('id'), 'body': msg.get('body')[:200], 'parsed': parsed})
    # Print concise output
    print('\n' + '='*60)
    print(f"Message ID: {msg.get('id')}")
    print(f"Body: {msg.get('body')[:200]}\n")
    print('Parsed:')
    print(json.dumps(parsed, ensure_ascii=False, indent=2))

# Save artifacts
out_dir = ROOT / 'artifacts'
out_dir.mkdir(exist_ok=True)
with open(out_dir / 'gemini_debug_output.json', 'w', encoding='utf-8') as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

logger.info('Wrote debug output for %d messages to %s', count, out_dir / 'gemini_debug_output.json')
print('\nDone. Wrote debug output to', str(out_dir / 'gemini_debug_output.json'))
