"""
Notification Service - Send alerts via WhatsApp (Whapi) / Discord
"""

import os
import json
import aiohttp
import asyncio
import logging
from typing import Optional, List
from datetime import datetime

logger = logging.getLogger("NotificationService")


class WhapiNotifier:
    """Send alerts via WhatsApp using Whapi"""

    def __init__(self, api_key: Optional[str] = None, phone_id: Optional[str] = None):
        self.api_key = api_key or os.getenv("WHAPI_API_KEY")
        self.phone_id = phone_id or os.getenv("WHAPI_PHONE_ID", "5318407744")
        self.enabled = bool(self.api_key)

    async def send(self, message: str, to_phone: Optional[str] = None):
        """Send message via WhatsApp"""
        if not self.enabled:
            logger.debug("Whapi not configured, skipping notification")
            return False

        to_phone = to_phone or self.phone_id
        url = "https://api.whapi.cloud/messages/text"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        data = {
            "to": to_phone,
            "body": message
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=data, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status in [200, 201]:
                        logger.info(f"WhatsApp message sent to {to_phone}")
                        return True
                    else:
                        error_text = await resp.text()
                        logger.error(f"Whapi error: {resp.status} - {error_text}")
                        return False
        except Exception as e:
            logger.error(f"Whapi send error: {e}")
            return False


class DiscordNotifier:
    """Send alerts to Discord"""

    def __init__(self, webhook_url: Optional[str] = None):
        self.webhook_url = webhook_url or os.getenv("DISCORD_WEBHOOK_URL")
        self.enabled = bool(self.webhook_url)

    async def send(self, message: str, title: str = "mavi-lojistik Alert"):
        """Send message to Discord"""
        if not self.enabled:
            logger.debug("Discord not configured, skipping notification")
            return False

        embed = {
            "title": title,
            "description": message,
            "color": 16711680 if "🔴" in message else 16776960,  # Red or Yellow
            "timestamp": datetime.now().isoformat(),
            "footer": {"text": "mavi-lojistik"}
        }

        data = {"embeds": [embed]}

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.webhook_url, json=data, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 204:
                        logger.info("Discord notification sent")
                        return True
                    else:
                        logger.error(f"Discord error: {resp.status}")
                        return False
        except Exception as e:
            logger.error(f"Discord send error: {e}")
            return False


class NotificationService:
    """
    Unified notification service for WhatsApp (Whapi), Discord, and other channels
    """

    def __init__(self):
        self.whapi = WhapiNotifier()
        self.discord = DiscordNotifier()

    async def send_alert(self, message: str, channels: List[str] = None):
        """
        Send alert to configured channels

        Args:
            message: Alert message
            channels: List of channels to send to (default: all configured)
        """
        if channels is None:
            channels = ["whapi", "discord"]

        results = {}

        if "whapi" in channels:
            results["whapi"] = await self.whapi.send(message)

        if "discord" in channels:
            results["discord"] = await self.discord.send(message)

        return results

    async def send_server_alert(self, alert_type: str, details: str):
        """Send formatted server alert"""
        message = f"🚨 *VPS ALERT: {alert_type}*\n\n{details}"
        await self.send_alert(message)

    async def send_operation_log(self, operation: str, status: str, output: str):
        """Log operation execution"""
        status_emoji = "✅" if status == "success" else "❌"
        message = f"{status_emoji} *{operation.upper()}*\nStatus: {status}\n\n{output[:200]}"
        await self.send_alert(message, channels=["whapi"])

    def is_configured(self) -> bool:
        """Check if any notification channel is configured"""
        return self.whapi.enabled or self.discord.enabled


# Global instance
_notification_service = None


def get_notification_service():
    global _notification_service
    if _notification_service is None:
        _notification_service = NotificationService()
    return _notification_service
