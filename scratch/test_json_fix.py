import os
import sys
from pathlib import Path

# Add src to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.utils.file_operations import load_json_safe, save_json_safe

def test_empty_file_loading():
    test_file = "scratch/empty_test.json"
    
    # 1. Test: Non-existent file
    if os.path.exists(test_file):
        os.remove(test_file)
    
    print("Testing non-existent file...")
    res = load_json_safe(test_file, default=[])
    assert res == [], f"Expected [], got {res}"
    print("OK")

    # 2. Test: 0-byte file
    print("Testing 0-byte file...")
    Path(test_file).touch()
    assert os.path.getsize(test_file) == 0
    
    res = load_json_safe(test_file, default=["default"])
    assert res == ["default"], f"Expected ['default'], got {res}"
    print("OK")

    # 3. Test: Corrupt JSON file (but not empty)
    print("Testing corrupt JSON file...")
    with open(test_file, 'w') as f:
        f.write("{invalid: json}")
    
    res = load_json_safe(test_file, default={"status": "fallback"})
    assert res == {"status": "fallback"}, f"Expected fallback dict, got {res}"
    print("OK")

    # Cleanup
    if os.path.exists(test_file):
        os.remove(test_file)

if __name__ == "__main__":
    try:
        test_empty_file_loading()
        print("\nAll tests PASSED! load_json_safe is now robust.")
    except Exception as e:
        print(f"\nTest FAILED: {e}")
        sys.exit(1)
