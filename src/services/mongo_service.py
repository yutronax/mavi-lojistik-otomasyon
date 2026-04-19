import os
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, date, timedelta
import threading
import time
from pymongo import MongoClient, UpdateOne, DESCENDING
from pymongo.errors import ConnectionFailure, PyMongoError
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

class MongoDataService:
    """
    Service for centralized data management using MongoDB.
    Replaces DataService's file-based storage with cloud/central database.
    """
    
    def __init__(self, uri: str = None):
        load_dotenv()
        self.uri = uri or os.getenv('MONGODB_URI')
        if not self.uri:
            raise ValueError("MONGODB_URI not found in environment variables.")
        
        # Local paths for compatibility for components that still expect them
        from src.utils.common import get_user_data_dir
        user_data_dir = get_user_data_dir()
        self.onaylananlar_file = str(user_data_dir / 'onaylanan_kayitlar.json')
        self.onaylanmamis_file = str(user_data_dir / 'onaylanmamis_ayristirilmis.json')
        self.onaylanmamis_log_file = str(user_data_dir / 'onaylanmamis_ayristirilmis_log.json')
        self.blacklist_file = str(user_data_dir / 'blacklist.json')

        try:
            self.client = MongoClient(self.uri, serverSelectionTimeoutMS=5000)
            # Check connection
            self.client.admin.command('ping')
            self.db = self.client.get_database('mavi_lojistik')
            logger.info("MongoDB connection successful.")
            
            # Collections
            self.shipments = self.db.get_collection('approved_shipments')
            self.inbox = self.db.get_collection('inbox')
            self.inbox_log = self.db.get_collection('inbox_log')
            self.groups = self.db.get_collection('chat_groups')
            self.blacklist = self.db.get_collection('blacklist')
            self.processed_hashes = self.db.get_collection('processed_hashes')
            self.config = self.db.get_collection('configuration')
            
            # Ensure Indexes
            self._ensure_indexes()
            
        except ConnectionFailure as e:
            logger.error(f"Could not connect to MongoDB: {e}")
            raise
        except Exception as e:
            logger.error(f"MongoDB initialization error: {e}")
            raise

    def _ensure_indexes(self):
        """Create necessary indexes for performance and uniqueness WITH TTL support."""
        try:
            # 1. Functional Indexes
            self.inbox.create_index("message_id", unique=True)
            self.inbox.create_index("message_timestamp")
            self.shipments.create_index("message_id")
            self.groups.create_index("id", unique=True)
            self.blacklist.create_index("keyword", unique=True)
            self.processed_hashes.create_index("hash", unique=True)
            
            # 2. TTL (Time-To-Live) Indexes for 24h cleanup (86400 seconds)
            # Inbox/Unprocessed
            self.inbox.create_index("createdAt", expireAfterSeconds=86400)
            # Inbox Log
            self.inbox_log.create_index("createdAt", expireAfterSeconds=86400)
            # Approved Shipments (Management Center)
            self.shipments.create_index("createdAt", expireAfterSeconds=86400)
            # Processed hashes (Duplicate prevention)
            self.processed_hashes.create_index("createdAt", expireAfterSeconds=86400)
            
            logger.info("MongoDB TTL & Performance indexes verified.")
        except PyMongoError as e:
            logger.warning(f"Error creating indexes: {e}")

    # ==================== UNPROCESSED MESSAGES (INBOX) ====================

    def load_unprocessed_messages(self, filter_today: bool = True) -> Dict[str, Dict]:
        """
        İşlenmemiş mesajları MongoDB inbox koleksiyonundan yükler.
        
        İşlev: MongoDB'deki ham mesajları çeker, kara liste ve günlük filtre uygular.
        Bağlantılar: self.inbox collection, load_blacklist.
        Gereklilik: Uzak veritabanındaki mesajların temizlenmiş olarak merkeze iletilmesini sağlar.
        Kritik Kurallar: Kara listedeki numaralar asla yüklenmemelidir. MongoDB _id alanı GUI uyumluluğu için kaldırılmalıdır.
        """
        try:
            query = {}
            if filter_today:
                # Get start of today as Unix timestamp (seconds)
                today_start = datetime.combine(date.today(), datetime.min.time())
                cutoff_ts = today_start.timestamp()
                
                # Use numeric comparison with $convert to be robust against string types
                query = {
                    "$or": [
                        {"message_timestamp": {"$gte": cutoff_ts}},
                        # Fallback for old records that might still be strings
                        {"message_timestamp": {"$gte": str(cutoff_ts)}}
                    ]
                }
            
            # Load blacklist for filtering
            blacklist = self.load_blacklist()
            
            cursor = self.inbox.find(query).sort("message_timestamp", DESCENDING)
            result = {}
            for doc in cursor:
                mid = doc.get('message_id')
                if not mid:
                    continue
                
                # --- BLACKLIST FILTER ---
                sender_num = doc.get('phone') or doc.get('sender')
                if not sender_num and 'message_info' in doc:
                    sender_num = doc['message_info'].get('sender')
                
                if sender_num:
                    from src.utils.phone_utils import is_phone_in_list
                    if is_phone_in_list(sender_num, blacklist):
                        logger.info(f"[BLOCK] MongoDB Blacklist Filter: Skipping message {mid} from {sender_num}")
                        continue

                # --- INTERNATIONAL/INVALID LOCATION FILTER ---
                if doc.get('invalid_location'):
                    logger.info(f"[MAP] MongoDB Foreign Location Filter: Skipping message {mid}")
                    continue

                # Remove MongoDB _id for GUI compatibility
                doc.pop('_id', None)
                # Convert string timestamp to float locally to avoid GUI issues
                ts = doc.get('message_timestamp')
                if isinstance(ts, str):
                    try:
                        doc['message_timestamp'] = float(ts)
                    except: pass
                result[mid] = doc
            
            logger.info(f"Loaded {len(result)} messages from MongoDB inbox.")
            return result
        except PyMongoError as e:
            logger.error(f"MongoDB load_unprocessed error: {e}")
            return {}

    def manual_reset_history(self, hours_back: float = 2.0) -> Dict[str, Any]:
        """Clear unprocessed messages older than X hours."""
        try:
            cutoff = datetime.now() - timedelta(hours=hours_back)
            cutoff_ts = str(cutoff.timestamp())
            
            result = self.inbox.delete_many({"message_timestamp": {"$lt": cutoff_ts}})
            logger.info(f"Manual reset: Deleted {result.deleted_count} old messages.")
            return {"status": "success", "count": result.deleted_count}
        except PyMongoError as e:
            logger.error(f"MongoDB manual_reset error: {e}")
            return {"status": "error", "message": str(e)}

    def save_unprocessed_messages(self, messages: Dict[str, Dict], merge: bool = True) -> bool:
        """Upsert messages into inbox collection."""
        if not messages:
            return True
        try:
            operations = []
            now = datetime.now()
            for mid, data in messages.items():
                # Ensure it has message_id and TTL timestamp
                data['message_id'] = mid
                if 'createdAt' not in data:
                    data['createdAt'] = now
                operations.append(
                    UpdateOne({"message_id": mid}, {"$set": data}, upsert=True)
                )
            
            if operations:
                self.inbox.bulk_write(operations)
                logger.info(f"Synchronized {len(operations)} messages to MongoDB inbox.")
            return True
        except PyMongoError as e:
            logger.error(f"MongoDB save_unprocessed error: {e}")
            return False

    def delete_unprocessed_message(self, message_id: str) -> bool:
        """Remove a message from inbox."""
        try:
            self.inbox.delete_one({"message_id": message_id})
            return True
        except PyMongoError as e:
            logger.error(f"MongoDB delete_unprocessed error: {e}")
            return False

    # ==================== APPROVED RECORDS (SHIPMENTS) ====================

    def load_approved_records(self, limit: int = 100) -> List[Dict]:
        """Load recently approved shipment records."""
        try:
            cursor = self.shipments.find().sort("approved_at", DESCENDING).limit(limit)
            result = []
            for doc in cursor:
                doc.pop('_id', None)
                result.append(doc)
            return result
        except PyMongoError as e:
            logger.error(f"MongoDB load_approved error: {e}")
            return []

    def save_approved_records(self, new_records: List[Dict]) -> bool:
        """Save new approved records to shipments collection."""
        if not new_records:
            return True
        try:
            now = datetime.now()
            for record in new_records:
                if 'approved_at' not in record:
                    record['approved_at'] = now.isoformat()
                
                # Ensure TTL timestamp
                if 'createdAt' not in record:
                    record['createdAt'] = now
                
                # Use message_id as a key if available to avoid duplicates
                mid = record.get('message_id')
                if mid:
                    self.shipments.update_one({"message_id": mid}, {"$set": record}, upsert=True)
                else:
                    self.shipments.insert_one(record)
            return True
        except PyMongoError as e:
            logger.error(f"MongoDB save_approved error: {e}")
            return False

    # ==================== GROUPS & BLACKLIST ====================

    def load_saved_groups(self) -> List[Dict]:
        """Load registered WhatsApp groups."""
        try:
            cursor = self.groups.find()
            result = []
            for doc in cursor:
                doc.pop('_id', None)
                result.append(doc)
            return result
        except PyMongoError as e:
            logger.error(f"MongoDB load_groups error: {e}")
            return []

    def save_groups(self, groups_list: List[Dict]) -> bool:
        """Overwrite groups collection with new list (or sync intelligently)."""
        try:
            # For simplicity, clear and re-insert, or use bulk upsert
            self.groups.delete_many({})
            if groups_list:
                # Remove any existing _id fields
                for g in groups_list: g.pop('_id', None)
                self.groups.insert_many(groups_list)
            return True
        except PyMongoError as e:
            logger.error(f"MongoDB save_groups error: {e}")
            return False

    def load_blacklist(self) -> List[str]:
        """Load blacklisted keywords."""
        try:
            cursor = self.blacklist.find()
            return [doc['keyword'] for doc in cursor if 'keyword' in doc]
        except PyMongoError as e:
            logger.error(f"MongoDB load_blacklist error: {e}")
            return []

    def save_blacklist(self, keywords: List[str]) -> bool:
        """Save blacklist to MongoDB."""
        try:
            # Use set for uniqueness
            unique_keywords = list(set(keywords))
            self.blacklist.delete_many({})
            if unique_keywords:
                docs = [{"keyword": kw} for kw in unique_keywords]
                self.blacklist.insert_many(docs)
            return True
        except PyMongoError as e:
            logger.error(f"MongoDB save_blacklist error: {e}")
            return False

    # ==================== CONFIGURATION (Cargo Types, etc) ====================

    def load_config(self, key: str, default: Any = None) -> Any:
        try:
            doc = self.config.find_one({"key": key})
            return doc.get('value', default) if doc else default
        except PyMongoError:
            return default

    def save_config(self, key: str, value: Any) -> bool:
        try:
            self.config.update_one({"key": key}, {"$set": {"value": value}}, upsert=True)
            return True
        except PyMongoError:
            return False

    def load_arac_kasa_tipleri(self) -> Dict[str, List[str]]:
        """Load vehicle and cargo types from MongoDB configuration."""
        default = {
            'arac_tipleri': [],
            'kasa_tipleri': [],
            'yuk_tipleri': []
        }
        return self.load_config('arac_kasa_tipleri', default)

    def save_arac_kasa_tipleri(self, data: Dict[str, List[str]]) -> bool:
        """Save vehicle and cargo types to MongoDB configuration."""
        return self.save_config('arac_kasa_tipleri', data)

    def load_il_ilceler(self) -> List[Dict]:
        """Load province/district data from MongoDB."""
        return self.load_config('il_ilceler', [])

    def save_il_ilceler(self, data: List[Dict]) -> bool:
        """Save province/district data to MongoDB."""
        return self.save_config('il_ilceler', data)

    def load_yuk_tipleri(self) -> List[str]:
        """Load cargo types separately if needed."""
        ak = self.load_arac_kasa_tipleri()
        return ak.get('yuk_tipleri', [])

    # ==================== CONTENT DEDUPLICATION ====================

    def _hash_content(self, text: str) -> str:
        """Helper to hash content identically across services."""
        import hashlib
        # Basit normalizasyon: boşlukları temizle ve küçük harfe çevir
        normalized = "".join(text.split()).lower()
        return hashlib.sha256(normalized.encode('utf-8')).hexdigest()

    def is_body_known(self, body_text: str) -> bool:
        """Check if message hash already exists in processed_hashes."""
        if not body_text:
            return False
        content_hash = self._hash_content(body_text)
        try:
            doc = self.processed_hashes.find_one({"hash": content_hash})
            if doc:
                # 1 saatlik pencere kontrolü (DataService ile uyumlu)
                from datetime import datetime, timedelta
                created_at = doc.get("createdAt")
                if created_at and datetime.now() - created_at < timedelta(hours=1):
                    return True
            return False
        except PyMongoError:
            return False

    def mark_content_as_processed(self, body_text: str) -> bool:
        """Store message hash to prevent duplicates."""
        if not body_text:
            return False
        content_hash = self._hash_content(body_text)
        try:
            from datetime import datetime
            self.processed_hashes.update_one(
                {"hash": content_hash}, 
                {"$set": {"hash": content_hash, "createdAt": datetime.now()}}, 
                upsert=True
            )
            return True
        except PyMongoError:
            return False

    def is_shipment_duplicate(self, shipment: Dict) -> bool:
        """
        Check if an identical shipment (same route + phone) exists in MongoDB from last 1 hour.
        Checks both 'shipments' (approved) and 'inbox' (unapproved) collections.
        """
        try:
            from datetime import datetime, timedelta
            cutoff = datetime.now() - timedelta(hours=1)
            
            # Common query fields
            query_base = {
                "nereden_il": shipment.get('nereden_il'),
                "nereden_ilce": shipment.get('nereden_ilce'),
                "nereye_il": shipment.get('nereye_il'),
                "nereye_ilce": shipment.get('nereye_ilce'),
                "telefon": shipment.get('telefon')
            }
            
            # Add complex fields to the unique identifier (sorted comparison)
            for field in ['arac_tipi', 'kasa_tipi', 'yuk_tipi']:
                val = shipment.get(field, [])
                if val:
                    query_base[field] = {"$all": sorted(val)} if isinstance(val, list) else val

            # 1. Check in 'shipments' (approved records)
            shipment_query = query_base.copy()
            shipment_query["message_timestamp"] = {"$gt": cutoff.timestamp()}
            if self.shipments.find_one(shipment_query):
                return True
                
            # 2. Check in 'inbox' (unapproved messages)
            inbox_query = {
                "message_timestamp": {"$gt": cutoff.timestamp()},
                "shipments": {"$elemMatch": query_base}
            }
            if self.inbox.find_one(inbox_query):
                return True
                
            return False
        except Exception as e:
            logger.error(f"MongoDB duplicate shipment check error: {e}")
            return False

    def cleanup_storage(self) -> Dict[str, Any]:
        """
        Deletes old local backups and temporary files to prevent storage bloat.
        Runs every 2 hours (via orchestrator).
        """
        import glob
        results = {"deleted_files": 0, "freed_bytes": 0, "errors": []}
        data_dir = os.path.dirname(self.onaylanmamis_file)
        
        try:
            now = time.time()
            day_in_seconds = 24 * 3600
            
            # 1. Delete .bak files older than 24 hours
            for f in glob.glob(os.path.join(data_dir, "*.bak*")):
                try:
                    if os.path.isfile(f) and (now - os.path.getmtime(f) > day_in_seconds):
                        size = os.path.getsize(f)
                        os.remove(f)
                        results["deleted_files"] += 1
                        results["freed_bytes"] += size
                except Exception as fe:
                    results["errors"].append(str(fe))

            # 2. Delete stale atomic .tmp files (older than 1 hour)
            for f in glob.glob(os.path.join(data_dir, ".atomic_*.tmp")):
                try:
                    if os.path.isfile(f) and (now - os.path.getmtime(f) > 3600):
                        size = os.path.getsize(f)
                        os.remove(f)
                        results["deleted_files"] += 1
                        results["freed_bytes"] += size
                except Exception as fe:
                    results["errors"].append(str(fe))
            
            logger.info(f"MongoDataService cleanup storage: freed {results['freed_bytes']} bytes across {results['deleted_files']} files.")
            return results
        except Exception as e:
            logger.error(f"Error during MongoDataService cleanup_storage: {e}")
            return results
