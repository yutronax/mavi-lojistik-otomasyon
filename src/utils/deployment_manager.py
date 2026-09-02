"""
Blue-Green Deployment Manager
Safe deployment with automatic rollback capability
"""

import os
import json
import shutil
import subprocess
import logging
from datetime import datetime
from typing import Tuple

logger = logging.getLogger("DeploymentManager")


class DeploymentManager:
    """
    Blue-Green deployment strategy:
    1. Create backup of current codebase before update
    2. Perform git pull
    3. Test deployment (health check)
    4. If failed, automatic rollback to backup
    5. Cleanup old backups
    """

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self.backup_dir = os.path.join(root_dir, "data", "deployment_backups")
        self.max_backups = 5  # Keep last 5 deployments
        os.makedirs(self.backup_dir, exist_ok=True)

    def create_backup(self) -> Tuple[bool, str]:
        """Create backup of current codebase"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"backup_{timestamp}"
            backup_path = os.path.join(self.backup_dir, backup_name)

            # Exclude large directories
            exclude_dirs = [".git", "__pycache__", ".pytest_cache", "venv", "node_modules"]

            # Create archive-like backup
            os.makedirs(backup_path, exist_ok=True)

            for item in os.listdir(self.root_dir):
                if item in exclude_dirs or item.startswith("."):
                    continue

                src = os.path.join(self.root_dir, item)
                dst = os.path.join(backup_path, item)

                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True, ignore=shutil.ignore_patterns(*exclude_dirs))
                else:
                    shutil.copy2(src, dst)

            logger.info(f"✅ Backup created: {backup_name}")

            # Save backup metadata
            metadata = {
                "timestamp": timestamp,
                "backup_name": backup_name,
                "git_commit": self._get_current_commit()
            }
            self._save_metadata(backup_path, metadata)

            return True, backup_path

        except Exception as e:
            logger.error(f"Backup creation failed: {e}")
            return False, str(e)

    def git_pull(self) -> Tuple[bool, str]:
        """Perform git pull"""
        try:
            result = subprocess.run(
                ["git", "pull"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("✅ Git pull successful")
                return True, result.stdout

            else:
                logger.error(f"Git pull failed: {result.stderr}")
                return False, result.stderr

        except Exception as e:
            logger.error(f"Git pull error: {e}")
            return False, str(e)

    def rollback(self, backup_path: str) -> Tuple[bool, str]:
        """Rollback to specific backup"""
        try:
            if not os.path.exists(backup_path):
                return False, "Backup not found"

            logger.info(f"🔄 Rolling back to {os.path.basename(backup_path)}")

            # Remove current files (except .git, venv, etc)
            for item in os.listdir(self.root_dir):
                if item in [".git", "venv", ".env", "data"]:
                    continue

                path = os.path.join(self.root_dir, item)
                if os.path.isdir(path):
                    shutil.rmtree(path)
                else:
                    os.remove(path)

            # Restore from backup
            for item in os.listdir(backup_path):
                src = os.path.join(backup_path, item)
                dst = os.path.join(self.root_dir, item)

                if os.path.isdir(src):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                else:
                    shutil.copy2(src, dst)

            logger.info("✅ Rollback successful")
            return True, "Rollback completed"

        except Exception as e:
            logger.error(f"Rollback failed: {e}")
            return False, str(e)

    def cleanup_old_backups(self):
        """Remove old backups, keep only last N"""
        try:
            backups = sorted(os.listdir(self.backup_dir))

            if len(backups) > self.max_backups:
                to_remove = len(backups) - self.max_backups

                for backup in backups[:to_remove]:
                    backup_path = os.path.join(self.backup_dir, backup)
                    shutil.rmtree(backup_path)
                    logger.info(f"🗑️ Removed old backup: {backup}")

        except Exception as e:
            logger.error(f"Cleanup error: {e}")

    def _get_current_commit(self) -> str:
        """Get current git commit hash"""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.root_dir,
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip() if result.returncode == 0 else "unknown"
        except:
            return "unknown"

    def _save_metadata(self, backup_path: str, metadata: dict):
        """Save backup metadata"""
        try:
            metadata_file = os.path.join(backup_path, ".backup_metadata.json")
            with open(metadata_file, "w") as f:
                json.dump(metadata, f, indent=2)
        except Exception as e:
            logger.error(f"Metadata save error: {e}")

    def get_backup_list(self) -> list:
        """Get list of available backups"""
        try:
            backups = []
            for backup_name in sorted(os.listdir(self.backup_dir), reverse=True):
                backup_path = os.path.join(self.backup_dir, backup_name)
                if os.path.isdir(backup_path):
                    metadata_file = os.path.join(backup_path, ".backup_metadata.json")
                    metadata = {}
                    if os.path.exists(metadata_file):
                        with open(metadata_file) as f:
                            metadata = json.load(f)

                    backups.append({
                        "name": backup_name,
                        "path": backup_path,
                        "timestamp": metadata.get("timestamp"),
                        "commit": metadata.get("git_commit")
                    })

            return backups

        except Exception as e:
            logger.error(f"Backup list error: {e}")
            return []


# Global instance
_deployment_manager = None


def get_deployment_manager(root_dir: str = None):
    global _deployment_manager
    if _deployment_manager is None:
        if root_dir is None:
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        _deployment_manager = DeploymentManager(root_dir)
    return _deployment_manager
