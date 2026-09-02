"""
Backup Scheduler - Scheduled automatic backups via APScheduler
"""

import os
import logging
from datetime import datetime, timedelta
from src.utils.deployment_manager import get_deployment_manager
from src.utils.notification_service import get_notification_service

logger = logging.getLogger("BackupScheduler")

try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    from apscheduler.triggers.cron import CronTrigger
    SCHEDULER_AVAILABLE = True
except ImportError:
    SCHEDULER_AVAILABLE = False
    logger.warning("APScheduler not installed - scheduled backups disabled")


class BackupScheduler:
    """Schedule automatic backups at regular intervals"""

    def __init__(self, root_dir: str = None):
        self.root_dir = root_dir or os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.deployment_mgr = get_deployment_manager(self.root_dir)

        if SCHEDULER_AVAILABLE:
            self.scheduler = AsyncIOScheduler()
        else:
            self.scheduler = None

    def setup_schedules(self):
        """Setup backup schedules"""
        if not self.scheduler:
            logger.error("Scheduler not available")
            return False

        try:
            # Daily backup at 2 AM
            self.scheduler.add_job(
                self._scheduled_backup,
                CronTrigger(hour=2, minute=0),
                id='daily_backup',
                name='Daily Backup at 2 AM',
                misfire_grace_time=600
            )
            logger.info("Scheduled daily backup at 02:00")

            # Weekly backup at Sunday 3 AM
            self.scheduler.add_job(
                self._scheduled_backup,
                CronTrigger(day_of_week=6, hour=3, minute=0),
                id='weekly_backup',
                name='Weekly Backup (Sunday 3 AM)',
                misfire_grace_time=600
            )
            logger.info("Scheduled weekly backup on Sunday at 03:00")

            return True

        except Exception as e:
            logger.error(f"Schedule setup error: {e}")
            return False

    async def _scheduled_backup(self):
        """Execute scheduled backup"""
        try:
            logger.info("Starting scheduled backup...")

            success, backup_path = self.deployment_mgr.create_backup()

            if success:
                backup_name = os.path.basename(backup_path)
                message = f"✅ Otomatik yedekleme başarılı\n📦 {backup_name}"
                logger.info(f"Backup successful: {backup_name}")
            else:
                message = f"❌ Yedekleme başarısız: {backup_path}"
                logger.error(f"Backup failed: {backup_path}")

            # Notify via Whapi
            try:
                notif = get_notification_service()
                await notif.send_alert(message, channels=["whapi"])
            except:
                pass

        except Exception as e:
            logger.error(f"Scheduled backup error: {e}")

            # Notify failure
            try:
                notif = get_notification_service()
                await notif.send_alert(f"❌ Yedekleme hatası: {str(e)[:100]}", channels=["whapi"])
            except:
                pass

    async def start(self):
        """Start the scheduler"""
        if not self.scheduler:
            logger.warning("Scheduler not available - backups will not be scheduled")
            return False

        try:
            if self.setup_schedules():
                self.scheduler.start()
                logger.info("Backup scheduler started")
                return True
        except Exception as e:
            logger.error(f"Scheduler start error: {e}")

        return False

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Backup scheduler stopped")

    def get_jobs(self):
        """Get list of scheduled jobs"""
        if not self.scheduler:
            return []

        jobs = []
        for job in self.scheduler.get_jobs():
            jobs.append({
                "id": job.id,
                "name": job.name,
                "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            })
        return jobs

    def get_backup_count(self):
        """Get total number of backups"""
        return len(self.deployment_mgr.get_backup_list())

    def get_backup_list(self):
        """Get list of all backups"""
        return self.deployment_mgr.get_backup_list()


# Global instance
_backup_scheduler = None


def get_backup_scheduler(root_dir: str = None):
    global _backup_scheduler
    if _backup_scheduler is None:
        _backup_scheduler = BackupScheduler(root_dir)
    return _backup_scheduler
