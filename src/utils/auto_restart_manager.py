"""
Auto-Restart Manager - Automatically restart service on crash
Monitors service health and triggers restart if down
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

logger = logging.getLogger("AutoRestartManager")


class AutoRestartManager:
    """
    Monitors service status and auto-restarts if it crashes
    - Check service status every N seconds
    - If down for more than X seconds, auto-restart
    - Maximum N restart attempts before giving up
    - Exponential backoff between restart attempts
    """

    def __init__(
        self,
        check_interval: int = 30,  # Check every 30 seconds
        down_threshold: int = 300,  # Restart if down for 5 minutes
        max_restart_attempts: int = 3,
        backoff_multiplier: float = 1.5
    ):
        self.check_interval = check_interval
        self.down_threshold = down_threshold
        self.max_restart_attempts = max_restart_attempts
        self.backoff_multiplier = backoff_multiplier

        self.is_running = False
        self.service_down_start: Optional[datetime] = None
        self.restart_count = 0
        self.last_restart = None
        self.callbacks = []  # For notifications

    def register_callback(self, callback: Callable):
        """Register callback for restart events"""
        self.callbacks.append(callback)

    async def start_monitoring(self, get_status_func: Callable, restart_func: Callable):
        """
        Start monitoring service health

        Args:
            get_status_func: Async function that returns status dict
            restart_func: Async function to restart the service
        """
        self.is_running = True
        logger.info("Auto-restart monitoring started")

        while self.is_running:
            try:
                stats = await get_status_func()
                status = stats.get("status", "offline")

                if status not in ["online", "running", "connected"]:
                    # Service is down
                    if self.service_down_start is None:
                        self.service_down_start = datetime.now()
                        logger.warning(f"Service detected as down at {self.service_down_start}")
                        await self._notify("⚠️ Servis çalışmıyor - 5 dakika sonra otomatik yeniden başlatılacak")
                    else:
                        # Check if down threshold exceeded
                        down_duration = datetime.now() - self.service_down_start
                        if down_duration.total_seconds() > self.down_threshold:
                            await self._attempt_restart(restart_func)
                else:
                    # Service is up, reset down timer
                    if self.service_down_start is not None:
                        down_duration = datetime.now() - self.service_down_start
                        logger.info(f"Service recovered after {down_duration.total_seconds()}s")
                        await self._notify(f"✅ Servis geri geldi ({int(down_duration.total_seconds())}s sonra)")
                        self.service_down_start = None
                        self.restart_count = 0  # Reset restart count on recovery

            except Exception as e:
                logger.error(f"Health check error: {e}")

            await asyncio.sleep(self.check_interval)

    async def _attempt_restart(self, restart_func: Callable):
        """Attempt to restart the service"""
        if self.restart_count >= self.max_restart_attempts:
            logger.error(f"Max restart attempts ({self.max_restart_attempts}) exceeded")
            await self._notify(f"🚨 Maksimum yeniden başlatma denemesi ({self.max_restart_attempts}) aşıldı - manuel müdahale gerekli")
            return

        self.restart_count += 1
        self.last_restart = datetime.now()

        logger.warning(f"Attempting auto-restart (attempt {self.restart_count}/{self.max_restart_attempts})")
        await self._notify(f"🔄 Servis otomatik yeniden başlatılıyor... (Deneme {self.restart_count}/{self.max_restart_attempts})")

        try:
            # Restart the service
            success, output = await restart_func()

            if success:
                logger.info("Auto-restart successful")
                await self._notify("✅ Servis başarıyla yeniden başlatıldı")
                self.service_down_start = None
                self.restart_count = 0
            else:
                logger.warning(f"Auto-restart failed: {output}")
                await self._notify(f"❌ Yeniden başlatma başarısız: {output[:100]}")

                # Wait before next attempt (exponential backoff)
                backoff_time = int(self.check_interval * (self.backoff_multiplier ** (self.restart_count - 1)))
                logger.info(f"Waiting {backoff_time}s before next restart attempt")
                await asyncio.sleep(backoff_time)

        except Exception as e:
            logger.error(f"Restart attempt error: {e}")
            await self._notify(f"❌ Yeniden başlatma hatası: {str(e)[:100]}")

    async def _notify(self, message: str):
        """Send notification to registered callbacks and Whapi"""
        # Send via Whapi
        try:
            from src.utils.notification_service import get_notification_service
            notif = get_notification_service()
            await notif.send_alert(message, channels=["whapi"])
        except Exception as e:
            logger.debug(f"Whapi notification skipped: {e}")

        # Call registered callbacks
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Callback error: {e}")

    def stop(self):
        """Stop monitoring"""
        self.is_running = False
        logger.info("Auto-restart monitoring stopped")

    def get_status(self) -> dict:
        """Get current auto-restart status"""
        return {
            "is_monitoring": self.is_running,
            "service_down": self.service_down_start is not None,
            "down_since": self.service_down_start.isoformat() if self.service_down_start else None,
            "restart_count": self.restart_count,
            "max_attempts": self.max_restart_attempts,
            "last_restart": self.last_restart.isoformat() if self.last_restart else None
        }


# Global instance
_auto_restart_manager = None


def get_auto_restart_manager(
    check_interval: int = 30,
    down_threshold: int = 300,
    max_attempts: int = 3
):
    global _auto_restart_manager
    if _auto_restart_manager is None:
        _auto_restart_manager = AutoRestartManager(
            check_interval=check_interval,
            down_threshold=down_threshold,
            max_restart_attempts=max_attempts
        )
    return _auto_restart_manager
