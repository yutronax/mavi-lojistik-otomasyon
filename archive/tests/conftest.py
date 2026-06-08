import os
import sys

# Ensure repository root is on sys.path so `import src...` works in tests
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Ensure tests run in test environment for toggles
os.environ.setdefault('ENVIRONMENT', 'test')
