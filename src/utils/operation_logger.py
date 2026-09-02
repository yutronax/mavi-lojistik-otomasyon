"""
Operation Logger - Tracks all server operations with timestamp and status
"""

import json
import os
from datetime import datetime
from typing import Dict, Any
import threading

class OperationLogger:
    """
    Logs all server operations with audit trail
    - Who (user/system)
    - What (command)
    - When (timestamp)
    - Result (success/fail)
    """

    def __init__(self, log_file=None):
        self.lock = threading.Lock()
        if log_file is None:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            log_file = os.path.join(root_dir, "data", "operation_log.json")
        self.log_file = log_file
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def log_operation(self, operation: str, result: str, details: Dict[str, Any] = None, user: str = "system"):
        """
        Log a server operation

        Args:
            operation: Operation name (e.g., "restart", "git_pull", "start")
            result: Result status ("success" or "failure")
            details: Additional details about the operation
            user: User who triggered the operation
        """
        with self.lock:
            try:
                logs = self._load_logs()

                entry = {
                    "timestamp": datetime.now().isoformat(),
                    "operation": operation,
                    "result": result,
                    "user": user,
                    "details": details or {}
                }

                logs.append(entry)

                # Keep only last 1000 operations to avoid massive files
                if len(logs) > 1000:
                    logs = logs[-1000:]

                with open(self.log_file, "w", encoding="utf-8") as f:
                    json.dump(logs, f, indent=2, ensure_ascii=False)

            except Exception as e:
                print(f"Operation logging error: {e}")

    def get_recent_operations(self, limit=50):
        """Get recent operations"""
        try:
            logs = self._load_logs()
            return logs[-limit:] if logs else []
        except Exception as e:
            print(f"Error reading operation logs: {e}")
            return []

    def get_failed_operations(self, limit=20):
        """Get recent failed operations"""
        try:
            logs = self._load_logs()
            failed = [op for op in logs if op.get('result') == 'failure']
            return failed[-limit:] if failed else []
        except Exception as e:
            print(f"Error reading failed operations: {e}")
            return []

    def _load_logs(self):
        """Load existing logs"""
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                return []
        return []


# Global instance
_operation_logger = None

def get_operation_logger():
    global _operation_logger
    if _operation_logger is None:
        _operation_logger = OperationLogger()
    return _operation_logger
