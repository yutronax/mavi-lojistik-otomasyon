"""
Data Service Module

Centralized data management for the Mavi Lojistik application.
Handles all file I/O operations with atomic writes and comprehensive error handling.
"""

import os
import json
import logging
from typing import Dict, List, Optional, Union, Any
from datetime import date, datetime, timedelta

from src.utils.file_operations import save_json_safe, load_json_safe
from src.services.persistence_manager import persistence_manager
from src.utils.config import DUPLICATE_CHECK_HOURS
import hashlib
import glob
import time

logger = logging.getLogger(__name__)


class DataService:
    """
    Centralized service for all data operations.
    
    Responsibilities:
    - Load/save unprocessed messages
    - Load/save approved records
    - Load configuration data (il/ilce, yuk types, etc.)
    - Atomic file operations with backups
    - Error handling and logging
    """
    
    def __init__(self, root_dir: str):
        """
        Initialize DataService with project root directory.
        
        Args:
            root_dir: Absolute path to project root
        """
        from src.utils.common import get_user_data_dir, get_bundled_data_dir
        
        self.root_dir = root_dir  # Legacy support
        self.data_dir = os.path.join(root_dir, 'data') # This seems to be a new addition, but the original code already defines user_data_dir
        
        # User Data (Writable) - Stored next to EXE
        user_data_dir = get_user_data_dir()
        self.user_data_dir = user_data_dir # Make user_data_dir an instance variable
        
        # Ensure directories exist
        os.makedirs(self.data_dir, exist_ok=True)
        os.makedirs(self.user_data_dir, exist_ok=True)
        
        self.blacklist_file = str(user_data_dir / 'blacklist.json')
        self.handled_ids_file = str(user_data_dir / 'handled_ids.json')
        self.onaylananlar_file = str(user_data_dir / 'onaylanan_kayitlar.json')
        self.onaylanmamis_file = str(user_data_dir / 'onaylanmamis_ayristirilmis.json')
        self.onaylanmamis_log_file = str(user_data_dir / 'onaylanmamis_ayristirilmis_log.json')

        # MongoDB Sync Support
        self.mongo_service = None
        mongodb_uri = os.getenv('MONGODB_URI')
        if mongodb_uri:
            try:
                from src.services.mongo_service import MongoDataService
                self.mongo_service = MongoDataService(mongodb_uri)
                logger.info("DataService: MongoDB sync enabled.")
            except Exception as e:
                logger.warning(f"DataService: MongoDB initialization failed (sync disabled): {e}")

        # --- CACHING FOR PERFORMANCE ---
        self._blacklist_cache: Optional[List[str]] = None
        self._blacklist_mtime: float = 0.0
        self._unprocessed_hashes_cache: Optional[set] = None
        self._unprocessed_hashes_mtime: float = 0.0
        self._handled_ids_cache: Optional[Dict[str, str]] = None
        self._handled_ids_mtime: float = 0.0
        
        # Also expose chat groups path
        self.chat_groups_file = str(user_data_dir / 'chat_groups.json')
        self.processed_contents_file = str(user_data_dir / 'processed_contents.json')
        
        # Bundled Data (Read-Only) - Stored in _internal/MEIPASS
        bundled_data_dir = get_bundled_data_dir()
        self.il_ilceler_file = str(bundled_data_dir / 'il_ilçe_mahalle.json')
        # Fallback to old file if new one doesn't exist (yet)
        if not os.path.exists(self.il_ilceler_file):
             self.il_ilceler_file = str(bundled_data_dir / 'il_ilçeler.json')

        self.yuk_tipi_file = str(bundled_data_dir / 'yuk_tipi.json')
        self.arac_kasa_file = str(bundled_data_dir / 'arac_yuk_kasa_tipleri.json')
        
        logger.info(f"DataService initialized.")
        logger.info(f"  User Data: {user_data_dir}")
        logger.info(f"  Bundled Data: {bundled_data_dir}")

        # Automatic Data Migration: Copy initial files from bundle to user dir if missing
        import shutil
        files_to_migrate = ['chat_groups.json', 'blacklist.json']
        for filename in files_to_migrate:
            user_file = user_data_dir / filename
            bundled_file = bundled_data_dir / filename
            
            if not user_file.exists() and bundled_file.exists():
                try:
                    shutil.copy2(bundled_file, user_file)
                    logger.info(f"Migrated initial data: {filename}")
                except Exception as e:
                    logger.error(f"Failed to migrate {filename}: {e}")
                    
        # Disk temizlik servisi artık DataService tarafından değil, orchestrator tarafından yönetiliyor
        # veya manuel olarak cleanup_storage() çağrılarak yapılıyor.
    
    # ==================== APP CONFIG ====================
    
    def save_config(self, key: str, value: Any):
        """
        Purpose:      Save a configuration dictionary under a given key
        Inputs:       key (str) - config section name, value (Any) - config data
        Outputs:      None
        Dependencies: file_operations.save_json_safe
        Usage:        Settings page saves Ollama/Whapi config
        """
        config_file = os.path.join(str(self.user_data_dir), 'app_config.json')
        try:
            # 1. Local Save
            existing = load_json_safe(config_file) or {}
            existing[key] = value
            save_json_safe(config_file, existing)
            
            # 2. MongoDB Sync
            if self.mongo_service:
                self.mongo_service.save_config(key, value)
                
            logger.info(f"Config saved & synced: {key}")
            return True
        except Exception as e:
            logger.error(f"Failed to save config '{key}': {e}")
            return False

    def load_config(self, key: str) -> Optional[Dict]:
        """
        Purpose:      Load a configuration dictionary by key
        Inputs:       key (str) - config section name
        Outputs:      dict or None
        Dependencies: file_operations.load_json_safe
        Usage:        Settings page loads Ollama/Whapi config
        """
        # 1. Try MongoDB first (Source of Truth for VPS/Cloud)
        if self.mongo_service:
            mongo_val = self.mongo_service.load_config(key)
            if mongo_val is not None:
                return mongo_val

        # 2. Fallback to Local File
        config_file = os.path.join(str(self.user_data_dir), 'app_config.json')
        try:
            data = load_json_safe(config_file) or {}
            return data.get(key)
        except Exception as e:
            logger.error(f"Failed to load config '{key}': {e}")
            return None

    # ==================== UNPROCESSED MESSAGES ====================
    
    def load_unprocessed_messages(self, filter_today: bool = True, hours_back: Optional[float] = None) -> Dict[str, Dict]:
        """
        Load unprocessed parsed messages.
        
        Args:
            filter_today: If True, only return today's messages (ignored if hours_back is set)
            hours_back: If set, only return messages from the last X hours
            
        Returns:
            Dictionary mapping message_id to message data
        """
        try:
            data = load_json_safe(self.onaylanmamis_file, default=[])
            
            if not isinstance(data, list):
                logger.warning(f"Expected list in {self.onaylanmamis_file}, got {type(data)}")
                return {}
            
            # Convert list to dict keyed by message_id
            result: Dict[str, Dict] = {}
            skipped: int = 0
            today = date.today()
            
            # Load processed hashes once to avoid recursion and improve performance
            processed_hashes = self.load_processed_content_hashes()
            
            # --- LOCAL RETENTION PURGE ---
            now_ts = time.time()
            # If hours_back provided, use it. Otherwise use 24h default.
            effective_hours = hours_back if hours_back is not None else 24.0
            cutoff_ts = now_ts - (effective_hours * 3600)
            any_purged = False
            
            # Load blacklist for filtering
            blacklist = self.load_blacklist()
            from src.utils.phone_utils import normalize_phone, is_phone_in_list

            for item in data:
                message_id = item.get('message_id')
                if not message_id:
                    continue
                
                # --- BLACKLIST FILTER ---
                # Check message_info or top-level sender fields
                sender_num = item.get('phone')
                if not sender_num and 'message_info' in item:
                    sender_num = item['message_info'].get('sender_number')
                if not sender_num:
                    sender_num = item.get('sender')
                
                if sender_num:
                    if is_phone_in_list(sender_num, blacklist):
                        logger.info(f"[BLOCK] Blacklist Filter: Skipping message {message_id} from {sender_num}")
                        continue

                # --- INTERNATIONAL/INVALID LOCATION FILTER ---
                valid_shipments = []
                for s in item.get('shipments', []):
                    if not s.get('invalid_location'):
                        valid_shipments.append(s)
                
                if not valid_shipments and item.get('shipments'):
                    logger.info(f"[MAP] Strict Foreign Location Filter: Skipping message {message_id} (All shipments foreign/invalid)")
                    continue
                
                # Sadece gecerli olanlari birak
                item['shipments'] = valid_shipments

                # Extract timestamp for retention check
                ts = None
                for k in ['message_timestamp', 'timestamp', 'createdAt', 'message_date']:
                    val = item.get(k)
                    if not val: continue
                    try:
                        if isinstance(val, (int, float)): ts = float(val)
                        elif isinstance(val, str): ts = datetime.fromisoformat(val.replace('Z', '+00:00')).timestamp()
                        if ts: break
                    except: continue

                # Check timestamp for retention
                if isinstance(ts, float) and ts < cutoff_ts:
                    any_purged = True
                    continue 
                
                # Double fallback check: if it's very old, confirm with Date extraction (only if no hours_back)
                if hours_back is None:
                    msg_date = self._extract_date(item)
                    if msg_date and msg_date < (date.today() - timedelta(days=1)):
                        any_purged = True
                        continue # Definite old record
                
                if not ts:
                    # If no timestamp found, don't purge yet, rely on filter_today
                    pass
                
                # Filter by date if requested (only if no hours_back)
                if hours_back is None and filter_today:
                    msg_date = self._extract_date(item)
                    if msg_date and msg_date != today:
                        skipped = skipped + 1
                        continue
                    if msg_date is None:
                        skipped = skipped + 1
                        continue
                
                result[message_id] = item
            
            if any_purged:
                logger.info("Auto-pruned very old records (>48h) from local store.")
            
            if skipped > 0:
                logger.debug(f"Filtered out {skipped} old/undated messages")
            
            logger.info(f"Loaded {len(result)} unprocessed messages")
            return result
            
        except Exception as e:
            logger.error(f"Error loading unprocessed messages: {e}", exc_info=True)
            return {}
    
    def save_unprocessed_messages(self, messages: Dict[str, Dict], merge: bool = False) -> bool:
        """
        Save unprocessed messages atomically with backup.
        
        Args:
            messages: Dictionary of message_id -> message data
            merge: If True, merges with existing file. If False (default), overwrites.
            
        Returns:
            True if successful, False otherwise
        """
        try:
            final_data = {}
            now_dt = datetime.now()

            if merge:
                # Merging logic to protect against concurrent webhook writes
                if os.path.exists(self.onaylanmamis_file):
                    existing_list = load_json_safe(self.onaylanmamis_file, default=[])
                    if isinstance(existing_list, list):
                        for msg in existing_list:
                            mid = msg.get('message_id') or msg.get('id')
                            if mid:
                                final_data[mid] = msg
                
                # Update with new messages
                for mid, msg_data in messages.items():
                    if 'createdAt' not in msg_data:
                        msg_data['createdAt'] = now_dt.timestamp()
                    final_data[mid] = msg_data
            else:
                # Direct Overwrite (GUI Mode)
                for mid, msg_data in messages.items():
                    if 'createdAt' not in msg_data:
                        msg_data['createdAt'] = now_dt.timestamp()
                final_data = messages

            # Convert dict to list for storage
            data_list = list(final_data.values())
            
            # Non-blocking, kilitlenme yapmayan yazma
            persistence_manager.queue_write(self.onaylanmamis_file, data_list, create_backup=True)
            
            logger.info(f"Saved {len(data_list)} unprocessed messages to background queue (Mode: {'Merge' if merge else 'Overwrite'})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save unprocessed messages: {e}", exc_info=True)
            return False
    
    def purge_old_messages(self, keep_only_today: bool = True) -> int:
        """
        Delete messages from local storage that are not from today.
        
        Args:
            keep_only_today: If True, deletes anything not matching today's date.
                             If False, defaults to stale 24h retention.
                             
        Returns:
            Number of messages purged
        """
        try:
            if not os.path.exists(self.onaylanmamis_file):
                return 0
                
            data = load_json_safe(self.onaylanmamis_file, default=[])
            if not data or not isinstance(data, list):
                return 0
                
            today = date.today()
            # DEFAULT RETENTION: 24 HOURS (TODAY ONLY)
            cutoff_ts = time.time() - (24 * 3600)
            
            kept_data: List[Dict] = []
            purged_count: int = 0
            
            for item in data:
                is_old = False
                
                if keep_only_today:
                    msg_date = self._extract_date(item)
                    if msg_date != today:
                        is_old = True
                else:
                    # Generic 24h fallback
                    ts = None
                    for k in ['message_timestamp', 'timestamp', 'createdAt', 'message_date']:
                        val = item.get(k)
                        if not val: continue
                        try:
                            if isinstance(val, (int, float)): ts = float(val)
                            elif isinstance(val, str): ts = datetime.fromisoformat(val.replace('Z', '+00:00')).timestamp()
                            if ts: break
                        except: continue
                    
                    if isinstance(ts, float) and ts < cutoff_ts:
                        is_old = True
                
                if is_old:
                    purged_count = purged_count + 1
                else:
                    kept_data.append(item)
            
            if purged_count > 0:
                logger.info(f"[OK] Purging {purged_count} old messages (Policy: {'Today Only' if keep_only_today else '24h'}).")
                persistence_manager.queue_write(self.onaylanmamis_file, kept_data)
            return purged_count
            
        except Exception as e:
            logger.error(f"Error during purge_old_messages: {e}")
            return 0

    def delete_unprocessed_message(self, message_id: str) -> bool:
        """Belirtilen ID'deki işlenmemiş mesajı diskten güvenle siler."""
        try:
            if not os.path.exists(self.onaylanmamis_file):
                return False
                
            data = load_json_safe(self.onaylanmamis_file, default=[])
            if not isinstance(data, list):
                return False
                
            original_len = len(data)
            kept_data = [d for d in data if d.get('message_id') != message_id and d.get('id') != message_id]
            
            if len(kept_data) < original_len:
                persistence_manager.queue_write(self.onaylanmamis_file, kept_data)
                logger.info(f"Deleted unprocessed message: {message_id}")
                return True
                
            return False
        except Exception as e:
            logger.error(f"Error deleting unprocessed message {message_id}: {e}")
            return False

    def append_unprocessed_log(self, entries: List[Dict]) -> bool:
        """
        Append entries to the historical unapproved parsed log file.
        Also performs minor cleanup and compression.
        """
        if not entries:
            return True
            
        try:
            # Load existing log
            log_data: List[Dict] = load_json_safe(self.onaylanmamis_log_file, default=[])
            if not isinstance(log_data, list):
                log_data = []
            
            # --- COMPRESSION: Remove heavy redundant fields from entries ---
            compressed_entries = []
            for entry in entries:
                # Shallow copy to avoid modifying original reference if used elsewhere
                comp = entry.copy()
                if 'shipments' in comp:
                    # Remove redundant/heavy fields from historical log shipments
                    ship_list = []
                    for s in comp['shipments']:
                        s_min = s.copy()
                        # These are often identical to 'body' or already in 'message_info'
                        for heavy_field in ['aciklama', 'orijinal_mesaj', 'original_message']:
                            if heavy_field in s_min: del s_min[heavy_field]
                        ship_list.append(s_min)
                    comp['shipments'] = ship_list
                compressed_entries.append(comp)

            # Append new entries
            log_data.extend(compressed_entries)
            
            # Keep only last 500 entries (User reported bloat, so we decrease from 2000)
            if len(log_data) > 500:
                log_data = list(log_data)[-500:]
            
            # Atomic write via background queue
            persistence_manager.queue_write(self.onaylanmamis_log_file, log_data)
            return True
        except Exception as e:
            logger.error(f"Failed to append to unprocessed log: {e}")
            return False

    def cleanup_storage(self) -> Dict[str, Any]:
        """
        Deletes old backups and temporary files to prevent storage bloat.
        Runs every 2 hours (via orchestrator).
        """
        deleted_files: int = 0
        freed_bytes: int = 0
        errors: List[str] = []
        data_dir = os.path.dirname(self.onaylanmamis_file)
        
        try:
            # 1. Delete .bak files older than 24 hours
            # Patterns: *.bak and *.bak* (for timestamped ones)
            # Support both root data dir and the new backups/ subdirectory
            backups_dir = os.path.join(data_dir, "backups")
            patterns = [
                os.path.join(data_dir, "*.bak"), 
                os.path.join(data_dir, "*.bak*"),
                os.path.join(backups_dir, "*.bak"),
                os.path.join(backups_dir, "*.bak*"),
                os.path.join(data_dir, "*.backup*"),
                os.path.join(backups_dir, "*.backup*")
            ]
            
            now = time.time()
            day_in_seconds = 24 * 3600
            
            for pattern in patterns:
                for f in glob.glob(pattern):
                    try:
                        if os.path.isfile(f) and (now - os.path.getmtime(f) > day_in_seconds):
                            size = os.path.getsize(f)
                            os.remove(f)
                            deleted_files = deleted_files + 1
                            freed_bytes = freed_bytes + size
                    except Exception as fe:
                        errors.append(str(fe))

            # 2. Delete stale .tmp files (older than 1 hour)
            for f in glob.glob(os.path.join(data_dir, ".atomic_*.tmp")):
                try:
                    if os.path.isfile(f) and (now - os.path.getmtime(f) > 3600):
                        size = os.path.getsize(f)
                        os.remove(f)
                        deleted_files = deleted_files + 1
                        freed_bytes = freed_bytes + size
                except Exception as fe:
                    errors.append(str(fe))

            # 3. Delete Whapi Groups Cache if older than 24h or too big
            cache_file = os.path.join(data_dir, "temp_groups_cache.json")
            if os.path.exists(cache_file):
                try:
                    f_mtime = os.path.getmtime(cache_file)
                    f_size = os.path.getsize(cache_file)
                    # Delete if older than 24h OR larger than 20MB
                    if (now - f_mtime > day_in_seconds) or (f_size > 20 * 1024 * 1024):
                        os.remove(cache_file)
                        deleted_files = deleted_files + 1
                        freed_bytes = freed_bytes + f_size
                        logger.info(f"Deleted large/stale groups cache: {f_size / 1024 / 1024:.1f} MB")
                except Exception as fe:
                    errors.append(str(fe))

            logger.info(f"Storage cleanup completed: {deleted_files} files removed, "
                        f"{freed_bytes / 1024:.1f} KB freed.")
            
        except Exception as e:
            logger.error(f"Cleanup storage failed: {e}")
            errors.append(str(e))
            
        return {"deleted_files": deleted_files, "freed_bytes": freed_bytes, "errors": errors}



    def purge_old_logs(self, hours_back: float = 1.0) -> Dict[str, Any]:
        """
        Delete log files older than X hours across various log directories.
        
        Args:
            hours_back: Number of hours to keep logs for. Defaults to 1.0.
            
        Returns:
            Dictionary with results of the purge operation.
        """
        deleted_files: int = 0
        freed_bytes: int = 0
        errors: List[str] = []
        now = time.time()
        cutoff_ts = now - (hours_back * 3600)
        
        # Directories to scan for logs
        log_dirs = [
            os.path.join(self.root_dir, 'logs'),
            os.path.join(self.root_dir, 'SISTEM_LOGLARI'),
            os.path.join(self.root_dir, 'tools'),
            self.root_dir
        ]
        
        # File patterns that typically represent log files in this project
        patterns = ['*.log', '*.log.*', 'build_log*.txt', '*_submission.log', 'orchestrator.log']
        
        logger.info(f"[CLEAN] Starting log purge (Target: older than {hours_back}h)...")
        
        for directory in log_dirs:
            if not os.path.exists(directory):
                continue
                
            for pattern in patterns:
                for fpath in glob.glob(os.path.join(directory, pattern)):
                    try:
                        if not os.path.isfile(fpath):
                            continue
                            
                        # Skip if file is currently being written to by this process's main logger
                        # (We can't easily check other processes, but we can check mtime)
                        mtime = os.path.getmtime(fpath)
                        
                        if mtime < cutoff_ts:
                            size = os.path.getsize(fpath)
                            os.remove(fpath)
                            deleted_files = deleted_files + 1
                            freed_bytes = freed_bytes + size
                            logger.debug(f"Removed old log: {os.path.basename(fpath)}")
                    except Exception as e:
                        # Log file might be locked by another process
                        errors.append(f"{os.path.basename(fpath)}: {str(e)}")
        
        if deleted_files > 0:
            logger.info(f"[OK] Log cleanup completed: {deleted_files} files removed, "
                        f"{freed_bytes / 1024:.1f} KB freed.")
        else:
            logger.debug("No old logs found to purge.")
            
        return {"deleted_files": deleted_files, "freed_bytes": freed_bytes, "errors": errors}

    def manual_reset_history(self, hours_back: float = 2.0) -> Dict[str, Any]:
        """
        Manually purges all stored message data, logs, and duplicate hashes 
        older than X hours (User Request). 
        Approved records are kept as they are considered intentional output.
        """
        
        now_ts = time.time()
        cutoff_ts = now_ts - (hours_back * 3600)
        results = {"files": {}, "total_removed": 0}
        
        def filter_list_by_ts(filepath, ts_keys):
            nonlocal results
            data = load_json_safe(filepath, default=[])
            if not isinstance(data, list): data = []
            
            original_count = len(data)
            kept = []
            for item in data:
                # Find any of the potential timestamp keys
                item_ts = None
                for k in ts_keys:
                    val = item.get(k)
                    if not val: continue
                    try:
                        # Handle string ISO dates or float/int timestamps
                        if isinstance(val, (int, float)):
                            item_ts = float(val)
                            break
                        elif isinstance(val, str):
                            # Try ISO format
                            item_ts = datetime.fromisoformat(val.replace('Z', '+00:00')).timestamp()
                            break
                    except: continue
                
                if item_ts and item_ts > cutoff_ts:
                    kept.append(item)
            
            removed = original_count - len(kept)
            if removed > 0:
                persistence_manager.queue_write(filepath, kept)
                results["files"][os.path.basename(filepath)] = {"removed": removed, "kept": len(kept)}
                results["total_removed"] += removed
            return removed

        # 1. Parsed results & Logs
        filter_list_by_ts(self.onaylanmamis_file, ['message_timestamp', 'timestamp', 'parse_timestamp'])
        filter_list_by_ts(self.onaylanmamis_log_file, ['message_timestamp', 'timestamp', 'parse_timestamp'])

        # 2. Raw Messages (from whapi_fetcher)
        raw_msg_file = os.path.join(os.path.dirname(self.onaylanmamis_file), 'mesajlar.json')
        if os.path.exists(raw_msg_file):
            raw_data = load_json_safe(raw_msg_file, default={})
            messages = raw_data.get('messages', [])
            original_count = len(messages)
            kept_messages = [m for m in messages if float(m.get('timestamp', 0)) > cutoff_ts]
            removed = original_count - len(kept_messages)
            if removed > 0:
                raw_data['messages'] = kept_messages
                persistence_manager.queue_write(raw_msg_file, raw_data)
                results["files"]["mesajlar.json"] = {"removed": removed, "kept": len(kept_messages)}
                results["total_removed"] += removed

        # 3. Duplicate hashes (processed_contents.json)
        if os.path.exists(self.processed_contents_file):
            hashes = load_json_safe(self.processed_contents_file, default={})
            original_count = len(hashes)
            new_hashes = {}
            for h, iso_ts in hashes.items():
                try:
                    ts = datetime.fromisoformat(iso_ts).timestamp()
                    if ts > cutoff_ts:
                        new_hashes[h] = iso_ts
                except: pass
            
            removed = original_count - len(new_hashes)
            if removed > 0:
                persistence_manager.queue_write(self.processed_contents_file, new_hashes)
                results["files"]["hashes"] = {"removed": removed}
                results["total_removed"] += removed

        # 4. Live Messages (if exists)
        live_msg_file = os.path.join(os.path.dirname(self.onaylanmamis_file), 'live_messages.json')
        if os.path.exists(live_msg_file):
             filter_list_by_ts(live_msg_file, ['timestamp', 'message_timestamp'])

        logger.info(f"Manual reset completed. Removed {results['total_removed']} old entries across {len(results['files'])} categories.")
        return results
    
    # ==================== APPROVED RECORDS ====================
    
    def load_approved_records(self) -> List[Dict]:
        """
        Load approved shipment records.
        
        Returns:
            List of approved records
        """
        try:
            data = load_json_safe(self.onaylananlar_file, default=[])
            
            if not isinstance(data, list):
                logger.warning(f"Expected list in {self.onaylananlar_file}, got {type(data)}")
                return []
            
            # --- LOCAL 24-HOUR RETENTION PURGE FOR APPROVED ---
            cutoff_ts = time.time() - (24 * 3600)
            
            filtered_data = []
            any_purged = False
            for record in data:
                ts = None
                for k in ['createdAt', 'approved_at', 'timestamp']:
                    val = record.get(k)
                    if not val: continue
                    try:
                        if isinstance(val, (int, float)): ts = float(val)
                        elif isinstance(val, str): ts = datetime.fromisoformat(val.replace('Z', '+00:00')).timestamp()
                        if ts: break
                    except: continue
                
                if isinstance(ts, float) and ts < cutoff_ts:
                    any_purged = True
                    continue
                filtered_data.append(record)
            
            if any_purged:
                logger.info(f"Purged {len(data) - len(filtered_data)} old approved records (24h limit)")
                data = filtered_data
            
            logger.info(f"Loaded {len(data)} approved records")
            return data
            
        except Exception as e:
            logger.error(f"Error loading approved records: {e}", exc_info=True)
            return []
    
    def save_approved(self, payload: Dict) -> bool:
        """
        Alias for save_approved_records to match Operation Center expectations.
        Extracts shipments from payload and saves them.
        """
        if not payload:
            return False
        shipments = payload.get('shipments', [])
        if not shipments and 'pickupCity' in payload:
            # Fallback if single shipment passed instead of payload
            shipments = [payload]
        return self.save_approved_records(shipments)

    def save_approved_record(self, record: Dict) -> bool:
        """
        Append a new approved record atomically.
        """
        return self.save_approved_records([record])

    def save_approved_records(self, new_records: List[Dict]) -> bool:
        """
        Append multiple new approved records atomically.
        
        Args:
            new_records: List of approved shipment records
            
        Returns:
            True if successful
        """
        if not new_records:
            return True

        try:
            # Load existing records
            records = self.load_approved_records()
            
            # Append new records with timestamp
            now_ts = time.time()
            for record in new_records:
                if 'createdAt' not in record:
                    record['createdAt'] = now_ts
            
            records.extend(new_records)
            
            # Atomic write via background queue
            persistence_manager.queue_write(self.onaylananlar_file, records, create_backup=True)
            
            logger.info(f"Saved {len(new_records)} approved records to background queue")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save approved records: {e}", exc_info=True)
            return False
    
    # ==================== CONFIGURATION DATA ====================
    
    def load_il_ilceler(self) -> List[Dict]:
        """
        Load province/district data.
        Check user config (app_config.json/Mongo) first, fallback to bundled file.
        Adapts format for backward compatibility while preserving new structure for Flet.
        """
        try:
            # 1. Try loading from config (User data or Mongo)
            data = self.load_config('il_ilce_mahalle')
            
            # 2. Fallback to local file if no config data
            if not data:
                data = load_json_safe(self.il_ilceler_file, default=[])
            
            if not isinstance(data, list):
                logger.error(f"Invalid format for il_ilce_mahalle data")
                return []
            
            # Check if this is the new format with 'ilceler' list of dicts
            if data and 'ilceler' in data[0] and isinstance(data[0]['ilceler'], list):
                logger.debug("Adapting new il_ilçe_mahalle format for multi-UI compatibility")
                adapted_data = []
                for item in data:
                    il_adi = item.get('il')
                    ilceler_struct = item.get('ilceler', [])
                    # Extract just the names for backward compatibility (used by older Tkinter code)
                    ilce_names = [d.get('ilce') for d in ilceler_struct if isinstance(d, dict) and 'ilce' in d]
                    
                    adapted_data.append({
                        "il": il_adi,
                        "ilce": ilce_names,      # Compatibility key
                        "ilçe": ilce_names,      # Legacy key (with turkish char)
                        "ilceler": ilceler_struct, # Raw structure for Flet (management_center)
                        "_raw_ilceler": ilceler_struct 
                    })
                return adapted_data
            
            logger.info(f"Loaded {len(data)} provinces")
            return data
            
        except Exception as e:
            logger.error(f"Error loading il/ilce data: {e}", exc_info=True)
            return []
    
    def load_yuk_tipleri(self) -> List[str]:
        """
        Load cargo type data.
        
        Returns:
            List of cargo types
        """
        try:
            data = load_json_safe(self.yuk_tipi_file, default=[])
            
            if not isinstance(data, list):
                logger.error(f"Invalid format in {self.yuk_tipi_file}")
                return []
            
            logger.info(f"Loaded {len(data)} cargo types")
            return data
            
        except Exception as e:
            logger.error(f"Error loading yuk tipi data: {e}", exc_info=True)
            return []
    
    def save_yuk_tipleri(self, data: List[Dict]) -> bool:
        """
        Save cargo type rules atomically.
        
        Args:
            data: List of cargo type rule dictionaries
            
        Returns:
            True if save was successful, False otherwise
        """
        try:
            return persistence_manager.queue_write(self.yuk_tipi_file, data)
        except Exception as e:
            logger.error(f"Failed to save yuk tipi data: {e}", exc_info=True)
            return False
    
    def load_arac_kasa_tipleri(self) -> Dict[str, List]:

        """
        Load vehicle and cargo box types.
        
        Returns:
            Dictionary with keys: arac_tipleri, kasa_tipleri, yuk_tipleri
        """
        default = {
            'arac_tipleri': [],
            'kasa_tipleri': [],
            'yuk_tipleri': []
        }
        
        try:
            data = load_json_safe(self.arac_kasa_file, default=default)
            
            if not isinstance(data, dict):
                logger.error(f"Invalid format in {self.arac_kasa_file}")
                return default
            
            # Validate structure
            for key in default.keys():
                if key not in data or not isinstance(data[key], list):
                    logger.warning(f"Missing or invalid key '{key}' in arac/kasa data")
                    data[key] = []
            
            logger.info(f"Loaded arac/kasa types: {len(data.get('arac_tipleri', []))} vehicles, "
                       f"{len(data.get('kasa_tipleri', []))} boxes")
            return data
            
        except Exception as e:
            logger.error(f"Error loading arac/kasa data: {e}", exc_info=True)
            return default
            
    def load_blacklist(self) -> List[str]:
        """Load blacklisted phone numbers (normalized) with caching."""
        try:
            if not os.path.exists(self.blacklist_file):
                return []
            
            mtime = os.path.getmtime(self.blacklist_file)
            if self._blacklist_cache is not None and mtime <= self._blacklist_mtime:
                return self._blacklist_cache
            
            data = load_json_safe(self.blacklist_file, default=[])
            self._blacklist_cache = data
            self._blacklist_mtime = mtime
            return data
        except Exception as e:
            logger.error(f"Error loading blacklist: {e}")
            return self._blacklist_cache or []

    def save_blacklist(self, blacklist: List[str]) -> bool:
        """Save blacklisted phone numbers and sync with MongoDB if available."""
        try:
            persistence_manager.queue_write(self.blacklist_file, sorted(list(set(blacklist))))
            success = True # Arka plana atıldığı için başarılı varsayıyoruz
            
            # Sync with MongoDB if service is attached
            if success and self.mongo_service:
                try:
                    self.mongo_service.save_blacklist(blacklist)
                    logger.info("Blacklist synchronized to MongoDB.")
                except Exception as e:
                    logger.error(f"Failed to sync blacklist to MongoDB: {e}")
                    # We still return True because local save succeeded
            
            return success
        except Exception as e:
            logger.error(f"Error saving blacklist: {e}")
            return False

    # ==================== GROUP MANAGEMENT ====================

    def load_saved_groups(self) -> List[Dict]:
        """Load registered WhatsApp groups from local file."""
        try:
            return load_json_safe(self.chat_groups_file, default=[])
        except Exception as e:
            logger.error(f"Error loading saved groups: {e}")
            return []

    def save_groups(self, groups_list: List[Dict]) -> bool:
        """Save registered WhatsApp groups to local file."""
        try:
            return persistence_manager.queue_write(self.chat_groups_file, groups_list)
        except Exception as e:
            logger.error(f"Error saving groups: {e}")
            return False

    # ==================== CONFIGURATION (COMPATIBILITY) ====================

    def load_config(self, key: str, default: Any = None) -> Any:
        """
        Load configuration value (MongoDB compatibility layer).
        Maps specific keys to their respective local files.
        """
        try:
            # General config fallback
            from src.utils.common import get_user_data_dir
            config_file = get_user_data_dir() / 'app_config.json'
            configs = load_json_safe(str(config_file), default={})
            return configs.get(key, default)
        except Exception as e:
            logger.error(f"Error loading config {key}: {e}")
            return default

    def save_config(self, key: str, value: Any) -> bool:
        """
        Save configuration value (MongoDB compatibility layer).
        Maps specific keys to their respective local files.
        """
        try:
            from src.utils.common import get_user_data_dir
            config_file = get_user_data_dir() / 'app_config.json'
            
            # config güncellemeleri için anlık okuma yapıyoruz (race condition için load_json_safe kilitli çalışır)
            configs = load_json_safe(str(config_file), default={})
            configs[key] = value
            
            # Yazma işlemini arka plana atıyoruz
            return persistence_manager.queue_write(str(config_file), configs)
        except Exception as e:
            logger.error(f"Error saving config {key}: {e}")
            return False

    # ==================== CONTENT DEDUPLICATION ====================

    def _normalize_and_hash(self, text: str, strict: bool = False) -> str:
        """Normalize text and return SHA256 hash."""
        if not text:
            return ""
        
        if strict:
            # 100% matching (only strip surrounding whitespace)
            normalized = text.strip()
        else:
            # SUPER NORMALIZATION for cross-group duplicate detection
            # 1. Lowercase and strip
            text = text.lower().strip()
            # 2. Remove all non-alphanumeric characters (including emojis and punctuation)
            import re
            # Keep letters and numbers only
            text = re.sub(r'[^a-z0-9]', '', text)
            # 3. Final string for hashing
            normalized = text
            
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def load_processed_content_hashes(self) -> Dict[str, str]:
        """Load hashes of processed message bodies with dates. Returns {hash: 'YYYY-MM-DD'}."""
        try:
            data = load_json_safe(self.processed_contents_file, default={})
            # Migration: If list (old format), ignore/clear it because we need dates
            if isinstance(data, list):
                logger.info("Migrating processed_contents from list to dict (clearing old history for strict daily check)")
                return {}
            return data
        except Exception as e:
            logger.error(f"Error loading processed contents: {e}")
            return {}

    def mark_content_as_processed(self, body_text: str) -> bool:
        """Mark a message body as processed for checking duplicates (Last 1 Hour rule)."""
        if not body_text:
            return False
        
        try:
            content_hash = self._normalize_and_hash(body_text, strict=True)
            if not content_hash:
                return False

            hashes = self.load_processed_content_hashes()
            now = datetime.now()
            
            # Update/Add hash with full timestamp
            hashes[content_hash] = now.isoformat()
            
            # Cleanup: Remove hashes older than 24 hours to keep file lean
            cutoff = now - timedelta(hours=24)
            keys_to_remove = []
            for k, v in hashes.items():
                try:
                    ts = datetime.fromisoformat(v)
                    if ts < cutoff:
                        keys_to_remove.append(k)
                except:
                    keys_to_remove.append(k)
            
            for k in keys_to_remove:
                del hashes[k]
            
            # Arka planda yaz
            persistence_manager.queue_write(self.processed_contents_file, hashes)
            return True
        except Exception as e:
            logger.error(f"Error saving processed content hash: {e}")
            return False

    def is_body_known(self, body_text: str) -> bool:
        """
        Check if message body has been seen in the LAST X HOURS (default 2h).
        Returns True if we should SKIP processing this message.
        """
        if not body_text:
            return False
            
        # USER REQUEST: Strict 100% matching check
        strict_hash = self._normalize_and_hash(body_text, strict=True)
        
        from datetime import datetime, timedelta
        now = datetime.now()
        
        # 1. Check Historical Processed
        hashes = self.load_processed_content_hashes()
        if strict_hash in hashes:
            try:
                processed_time = datetime.fromisoformat(hashes[strict_hash])
                # Ensure at least 2 hours window if config is lower, but follow config if higher
                window_hours = max(2.0, float(DUPLICATE_CHECK_HOURS))
                if now - processed_time < timedelta(hours=window_hours):
                    return True
            except:
                pass
            
        # 2. Check Active (Current Queue/Unprocessed file) - CACHED
        try:
            mtime = 0
            if os.path.exists(self.onaylanmamis_file):
                mtime = os.path.getmtime(self.onaylanmamis_file)
            
            # Rebuild hash cache if file changed
            if self._unprocessed_hashes_cache is None or mtime > self._unprocessed_hashes_mtime:
                self._unprocessed_hashes_cache = set()
                active_list = load_json_safe(self.onaylanmamis_file, default=[])
                if isinstance(active_list, list):
                    for msg in active_list:
                        msg_body = msg.get('body') or msg.get('message_info', {}).get('body')
                        if msg_body:
                            # Cache strict for active items
                            s_h = self._normalize_and_hash(msg_body, strict=True)
                            if self._unprocessed_hashes_cache is not None:
                                self._unprocessed_hashes_cache.add(s_h)
                self._unprocessed_hashes_mtime = float(mtime)
            
            if self._unprocessed_hashes_cache is not None:
                if strict_hash in self._unprocessed_hashes_cache:
                    return True

        except Exception as e:
            logger.error(f"Error checking active messages for body duplicate: {e}")
            
        return False
    
    # ==================== HELPER METHODS ====================
    
    def _extract_date(self, item: Dict) -> Optional[date]:
        """
        Extract date from message item.
        
        Tries multiple fields in order of preference:
        1. message_timestamp (raw Unix timestamp)
        2. parse_timestamp
        3. timestamp_readable
        
        Args:
            item: Message dictionary
            
        Returns:
            date object or None if not found/parseable
        """
        from datetime import datetime
        
        # Try message_timestamp first (most reliable)
        ts = item.get('message_timestamp') or item.get('timestamp') or item.get('createdAt')
        if ts:
            try:
                # Handle both seconds and milliseconds
                ts_val = float(ts)
                if ts_val > 10**12: # Milliseconds (e.g. 1741511251337)
                    ts_val = ts_val / 1000
                elif ts_val > 10**10: # Likely milliseconds but smaller?
                    ts_val = ts_val / 1000
                    
                dt = datetime.fromtimestamp(ts_val)
                # Sanity check: if it's in the future or way in the past (before 2024), it's invalid
                if 1704067200 < ts_val < (time.time() + 86400):
                    return dt.date()
            except (ValueError, TypeError, OSError):
                pass
        
        # Try parse_timestamp or search for date strings
        for k in ['parse_timestamp', 'message_date', 'timestamp_readable']:
            val = item.get(k)
            if not val or not isinstance(val, str): continue
            try:
                # Try simple ISO
                if 'T' in val:
                    dt = datetime.fromisoformat(val.split('.')[0].replace('Z', '+00:00'))
                    return dt.date()
                # Try space-separated "YYYY-MM-DD HH:MM:SS"
                elif ' ' in val:
                    dt = datetime.strptime(val.split('.')[0], "%Y-%m-%d %H:%M:%S")
                    return dt.date()
            except (ValueError, TypeError):
                continue
        
        # Try message_info nested structure
        msg_info = item.get('message_info', {})
        if isinstance(msg_info, dict):
            ts = msg_info.get('timestamp')
            if ts:
                try:
                    ts_val = float(ts)
                    if ts_val > 10**12: ts_val /= 1000
                    dt = datetime.fromtimestamp(ts_val)
                    return dt.date()
                except:
                    pass
        
        return None

    # ==================== HANDLED MESSAGE IDS (Persistent ID Check) ====================
    
    def load_handled_ids(self) -> Dict[str, str]:
        """Load IDs of messages that have been processed or skipped. Returns {id: 'ISO_TS'}."""
        try:
            if not os.path.exists(self.handled_ids_file):
                return {}
            
            mtime = os.path.getmtime(self.handled_ids_file)
            if self._handled_ids_cache is not None and mtime <= self._handled_ids_mtime:
                return self._handled_ids_cache
            
            data = load_json_safe(self.handled_ids_file, default={})
            if not isinstance(data, dict): data = {}
            
            self._handled_ids_cache = data
            self._handled_ids_mtime = mtime
            return data
        except Exception as e:
            logger.error(f"Error loading handled IDs: {e}")
            return self._handled_ids_cache or {}

    def is_id_handled(self, msg_id: str) -> bool:
        """Check if message ID has been handled in the last 24 hours."""
        if not msg_id: return False
        try:
            ids = self.load_handled_ids()
            return msg_id in ids
        except: return False

    def mark_id_handled(self, msg_id: str) -> bool:
        """Mark a message ID as handled permanently (lasts 24h)."""
        if not msg_id: return False
        try:
            # Load current state
            ids = self.load_handled_ids().copy()
            now = datetime.now()
            ids[msg_id] = now.isoformat()
            
            # Prune older than 24h
            cutoff = now - timedelta(hours=24)
            to_del = []
            for k, v in ids.items():
                try:
                    if datetime.fromisoformat(v) < cutoff: to_del.append(k)
                except: to_del.append(k)
            
            for k in to_del: del ids[k]
            
            # Update cache
            self._handled_ids_cache = ids
            self._handled_ids_mtime = time.time()
            
            # Write to disk
            persistence_manager.queue_write(self.handled_ids_file, ids)
            return True
        except Exception as e:
            logger.error(f"Error marking ID as handled: {e}")
            return False
    
    def get_file_stats(self) -> Dict[str, Dict]:
        """
        Get statistics about all data files.
        
        Returns:
            Dictionary with file stats
        """
        stats: Dict[str, Dict[str, Any]] = {}
        
        files = {
            'unprocessed': self.onaylanmamis_file,
            'approved': self.onaylananlar_file,
            'il_ilceler': self.il_ilceler_file,
            'yuk_tipi': self.yuk_tipi_file,
            'arac_kasa': self.arac_kasa_file
        }
        
        for name, filepath in files.items():
            if os.path.exists(filepath):
                size = os.path.getsize(filepath)
                mtime = os.path.getmtime(filepath)
                stats[name] = {
                    'exists': True,
                    'size_bytes': size,
                    'size_kb': round(size / 1024, 2),
                    'modified': mtime
                }
            else:
                stats[name] = {'exists': False}
        
        return stats

    def _get_shipment_fingerprint(self, shipment: Dict) -> str:
        """
        Bir sevkiyat için benzersiz bir parmak izi oluşturur.
        
        İşlev: Sevkiyatın numara, rota ve yük tiplerini birleştirerek hash'lenebilir bir string üretir.
        Bağlantılar: is_shipment_duplicate, remove_shipment_duplicates.
        Gereklilik: Mükerrer sevkiyatların tespiti için benzersiz kimlik görevi görür.
        Kritik Kurallar: Telefon, nereden_il, nereye_il ve tüm tip alanları (araç/kasa/yük) dahil edilmelidir.
        """
        def get_fp_part(key):
            val = shipment.get(key)
            if isinstance(val, list):
                vals = sorted([str(v).lower().strip() for v in val if v])
                return ",".join(vals)
            return str(val or '').lower().strip()

        # Phone normalization for fingerprint consistency (Base 10 digits: 5xx...)
        from src.utils.phone_utils import get_phone_variants
        tel_variants = get_phone_variants(shipment.get('telefon', ''))
        tel_base = tel_variants[1] if len(tel_variants) > 1 else (tel_variants[0] if tel_variants else '')

        fp_parts = [
            str(shipment.get('nereden_il', '')).lower().strip(),
            str(shipment.get('nereden_ilce', '')).lower().strip(),
            str(shipment.get('nereye_il', '')).lower().strip(),
            str(shipment.get('nereye_ilce', '')).lower().strip(),
            tel_base,
            get_fp_part('arac_tipi'),
            get_fp_part('kasa_tipi'),
            get_fp_part('yuk_tipi')
        ]
        # Remove any whitespace within parts for extreme tolerance
        return "|".join(["".join(f.split()) for f in fp_parts])

    def is_shipment_approved(self, shipment: Dict) -> bool:
        """
        Check if the shipment exists in the approved records within the duplicate check window.
        """
        try:
            fingerprint = self._get_shipment_fingerprint(shipment)
            if not fingerprint or len(fingerprint.replace('|', '')) < 5:
                return False
                
            from datetime import datetime, timedelta
            window_hours = max(1.0, float(DUPLICATE_CHECK_HOURS))
            cutoff = datetime.now() - timedelta(hours=window_hours)
            
            approved = self.load_approved_records()
            for rec in approved:
                ts = rec.get('approved_at') or rec.get('createdAt')
                try:
                    if isinstance(ts, str):
                        try:
                            rec_dt = datetime.fromisoformat(ts.replace('Z', '+00:00'))
                        except:
                            rec_dt = datetime.fromtimestamp(float(ts))
                    else:
                        rec_dt = datetime.fromtimestamp(float(ts))
                    
                    if rec_dt < cutoff:
                        continue
                        
                    if self._get_shipment_fingerprint(rec) == fingerprint:
                        return True
                except:
                    continue
            return False
        except Exception as e:
            logger.error(f"Error checking is_shipment_approved: {e}")
            return False

    def is_shipment_unapproved(self, shipment: Dict) -> bool:
        """
        Check if the shipment exists in the unapproved records within the duplicate check window.
        """
        try:
            fingerprint = self._get_shipment_fingerprint(shipment)
            if not fingerprint or len(fingerprint.replace('|', '')) < 5:
                return False
                
            from datetime import datetime, timedelta
            window_hours = max(1.0, float(DUPLICATE_CHECK_HOURS))
            cutoff = datetime.now() - timedelta(hours=window_hours)
            
            unapproved = load_json_safe(self.onaylanmamis_file, default=[])
            if isinstance(unapproved, list):
                for msg_entry in unapproved:
                    ts = msg_entry.get('message_timestamp')
                    try:
                        if datetime.fromtimestamp(float(ts)) < cutoff:
                            continue
                    except:
                        continue
                    
                    for s in msg_entry.get('shipments', []):
                        if self._get_shipment_fingerprint(s) == fingerprint:
                            return True
            return False
        except Exception as e:
            logger.error(f"Error checking is_shipment_unapproved: {e}")
            return False

    def is_shipment_duplicate(self, shipment: Dict) -> bool:
        """
        Aynı gün içinde birebir aynı sevkiyatın yapılıp yapılmadığını kontrol eder.
        Hem onaylanmamış (inbox) hem de onaylanmış (approved) kayıtları kontrol eder.
        """
        return self.is_shipment_unapproved(shipment) or self.is_shipment_approved(shipment)

    def remove_shipment_duplicates(self, shipment: Dict) -> int:
        """
        Parmak izi eşleşen tüm mükerrer ilanları onaylanmamış listesinden siler.
        
        İşlev: Verilen ilanın birebir kopyalarını son 24 saatlik veride arar ve bulursa siler.
        Bağlantılar: _get_shipment_fingerprint, self.onaylanmamis_file, persistence_manager.queue_write.
        Gereklilik: Agresif temizlik modu aktif olduğunda eski mükerrerlerin veri tabanından kalıcı olarak kaldırılması için kullanılır.
        Kritik Kurallar: Sadece son 24 saatteki ilanlar etkilenmelidir. Yazma işlemi atomik olmalıdır.
        """
        try:
            fingerprint = self._get_shipment_fingerprint(shipment)
            if not fingerprint or len(fingerprint.replace('|', '')) < 5:
                return 0
                
            data = load_json_safe(self.onaylanmamis_file, default=[])
            if not isinstance(data, list):
                return 0
                
            from datetime import datetime, timedelta
            # Policy change: same day = last 24 hours
            cutoff = datetime.now() - timedelta(hours=24)
            
            removed_total: int = 0
            new_data: List[Dict] = []
            
            for msg_entry in data:
                ts = msg_entry.get('message_timestamp')
                try:
                    msg_time = datetime.fromtimestamp(float(ts))
                except:
                    new_data.append(msg_entry)
                    continue
                
                if msg_time < cutoff:
                    new_data.append(msg_entry)
                    continue
                
                # Filter individual shipments within this message entry
                original_count = len(msg_entry.get('shipments', []))
                filtered_shipments = [
                    s for s in msg_entry.get('shipments', []) 
                    if self._get_shipment_fingerprint(s) != fingerprint
                ]
                
                removed_in_msg = original_count - len(filtered_shipments)
                if removed_in_msg > 0:
                    removed_total = removed_total + removed_in_msg
                    msg_entry['shipments'] = filtered_shipments
                    msg_entry['total_shipments'] = len(filtered_shipments)
                    
                    # If message now has NO shipments, we keep it as a 'duplicate' shell to track ID
                    if not filtered_shipments:
                        msg_entry['status'] = 'duplicate'
                
                new_data.append(msg_entry)
            
            if removed_total > 0:
                persistence_manager.queue_write(self.onaylanmamis_file, new_data)
                logger.info(f"[CLEAN] Aggressive Duplicate Check: Removed {removed_total} existing copies from storage.")
            
            return removed_total
        except Exception as e:
            logger.error(f"Error removing shipment duplicates: {e}")
            return 0
