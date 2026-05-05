
import os
import sys

# Proje kök dizinini belirle
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, ".."))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from src.utils.server_manager import ServerManager

def test_logs():
    print(f"Root Dir: {root_dir}")
    print("Testing server log retrieval...")
    manager = ServerManager()
    
    # Try to get logs
    logs = manager.get_logs(lines=10)
    print("\n--- SERVER LOGS ---")
    print(logs)
    print("--- END LOGS ---\n")

if __name__ == "__main__":
    test_logs()
