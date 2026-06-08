"""
Command Rate Limiter - Prevents abuse of server commands
"""

import time
from typing import Dict, Tuple
from collections import defaultdict


class CommandRateLimiter:
    """
    Rate limiter for server commands
    - Max 5 restart/pull commands per minute
    - Max 10 total commands per minute
    - Cooldown between operations
    """

    def __init__(self):
        self.operation_times: Dict[str, list] = defaultdict(list)
        self.last_operation_time: Dict[str, float] = {}

    def is_allowed(self, command: str) -> Tuple[bool, str]:
        """
        Check if command is allowed

        Returns:
            (allowed: bool, message: str)
        """
        current_time = time.time()

        # Expensive commands: restart, git_pull (max 5/min)
        expensive_commands = ["restart", "git_pull"]
        # All commands: max 10/min
        all_commands = ["restart", "stop", "start", "git_pull"]

        if command in expensive_commands:
            # Check expensive command limit (5 per minute)
            one_minute_ago = current_time - 60
            recent = [t for t in self.operation_times[command] if t > one_minute_ago]

            if len(recent) >= 5:
                next_allowed = recent[0] + 60
                wait_time = int(next_allowed - current_time)
                return False, f"Çok sık kullanıldı. {wait_time}sn sonra tekrar deneyin."

        if command in all_commands:
            # Check all command limit (10 per minute)
            one_minute_ago = current_time - 60
            all_recent = []
            for cmd in all_commands:
                all_recent.extend([t for t in self.operation_times[cmd] if t > one_minute_ago])

            if len(all_recent) >= 10:
                return False, "Çok hızlı işlem. Lütfen biraz bekleyin."

        # Cooldown check (minimum 5 seconds between operations)
        if command in self.last_operation_time:
            elapsed = current_time - self.last_operation_time[command]
            if elapsed < 5:
                return False, f"Lütfen {int(5 - elapsed)}sn bekleyin."

        return True, "Allowed"

    def record_operation(self, command: str):
        """Record that command was executed"""
        current_time = time.time()
        self.operation_times[command].append(current_time)
        self.last_operation_time[command] = current_time

        # Cleanup old entries (older than 2 minutes)
        two_minutes_ago = current_time - 120
        for cmd in self.operation_times:
            self.operation_times[cmd] = [t for t in self.operation_times[cmd] if t > two_minutes_ago]

    def get_status(self) -> Dict[str, any]:
        """Get current rate limit status"""
        current_time = time.time()
        one_minute_ago = current_time - 60

        status = {}
        for cmd in ["restart", "git_pull", "stop", "start"]:
            recent_count = len([t for t in self.operation_times[cmd] if t > one_minute_ago])
            status[cmd] = {
                "count": recent_count,
                "max": 5 if cmd in ["restart", "git_pull"] else 10
            }

        return status


# Global instance
_rate_limiter = None


def get_rate_limiter():
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = CommandRateLimiter()
    return _rate_limiter
