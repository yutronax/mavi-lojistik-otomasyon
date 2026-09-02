"""
Health Monitor - Tracks server health and sends alerts via WhatsApp
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Callable, Optional

logger = logging.getLogger("HealthMonitor")


async def _send_whapi_alert(message: str):
    """Send alert via Whapi if configured"""
    try:
        from src.utils.notification_service import get_notification_service
        notif_service = get_notification_service()
        await notif_service.send_alert(message, channels=["whapi"])
    except Exception as e:
        logger.error(f"Failed to send Whapi alert: {e}")


class HealthMonitor:
    """
    Monitors server health and triggers alerts
    - CPU > 80%
    - Memory > 85%
    - Disk > 90%
    - Service down for more than 5 minutes
    """

    def __init__(self, check_interval=60):
        self.check_interval = check_interval
        self.is_running = False
        self.last_alert_time = {}
        self.alert_cooldown = 300  # 5 minutes between same alerts
        self.callbacks = []
        self.service_down_start = None

    def register_alert_callback(self, callback: Callable):
        """Register callback for alerts (e.g., send Telegram message)"""
        self.callbacks.append(callback)

    async def monitor_health(self, get_status_func: Callable):
        """
        Continuously monitor server health

        Args:
            get_status_func: Async function that returns status dict
        """
        self.is_running = True

        while self.is_running:
            try:
                stats = await get_status_func()
                await self._check_health(stats)
            except Exception as e:
                logger.error(f"Health check error: {e}")

            await asyncio.sleep(self.check_interval)

    async def _check_health(self, stats: Dict):
        """Check health metrics and trigger alerts"""
        alerts = []

        # Check service status
        status = stats.get("status", "unknown")
        if status not in ["online", "running", "connected"]:
            if self.service_down_start is None:
                self.service_down_start = datetime.now()
                alerts.append(f"🔴 SERVİS DIŞI: Servis çalışmıyor (status: {status})")
            else:
                down_duration = datetime.now() - self.service_down_start
                if down_duration > timedelta(minutes=5):
                    alerts.append(f"🔴 SERVİS DIŞI: 5+ dakika hizmet dışı")
        else:
            self.service_down_start = None

        # Check CPU
        cpu = stats.get("cpu", 0)
        if cpu > 80:
            alerts.append(f"⚠️ YÜKSEK CPU: {cpu}% - İşlemleri kontrol edin")

        # Check Memory
        memory = stats.get("memory", 0)
        if memory > 85:
            alerts.append(f"⚠️ YÜKSEK BELLEK: {int(memory)}% - Temizleme gerekli")

        # Check Disk
        disk = stats.get("disk", 0)
        if disk > 90:
            alerts.append(f"🔴 DISK DOLU: {disk}% - Acil temizleme gerekli!")

        # Check System Memory (from system metrics)
        system = stats.get("system", {})
        sys_memory = system.get("memory_percent", 0)
        if sys_memory > 90:
            alerts.append(f"🔴 SİSTEM BELLEĞI DOLU: {int(sys_memory)}%")

        # Send alerts
        for alert in alerts:
            await self._send_alert(alert)

    async def _send_alert(self, message: str):
        """Send alert through registered callbacks and Whapi"""
        alert_key = message.split(":")[0]  # Use first part as key
        current_time = datetime.now()

        # Check cooldown
        last_time = self.last_alert_time.get(alert_key)
        if last_time and (current_time - last_time).total_seconds() < self.alert_cooldown:
            return  # Skip if recently alerted

        self.last_alert_time[alert_key] = current_time

        logger.warning(f"ALERT: {message}")

        # Send via Whapi by default
        await _send_whapi_alert(message)

        # Call registered callbacks
        for callback in self.callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Alert callback error: {e}")

    def stop(self):
        """Stop monitoring"""
        self.is_running = False


# Global instance
_health_monitor = None


def get_health_monitor():
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = HealthMonitor()
    return _health_monitor
