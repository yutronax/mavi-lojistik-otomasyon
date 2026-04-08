import os
import json
import logging
import sys
from datetime import datetime

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
sys.path.insert(0, root_dir)

from src.services.mongo_service import MongoDataService
from src.services.data_service import DataService

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def migrate():
    try:
        mongo = MongoDataService()
        local = DataService(root_dir)
        
        logger.info("Starting migration from JSON to MongoDB...")

        # 1. Migrate Chat Groups
        logger.info("Migrating Chat Groups...")
        from src.utils.file_ops import safe_json_load
        groups = safe_json_load(local.chat_groups_file, default=[])
        if groups:
            mongo.save_groups(groups)
            logger.info(f"Successfully migrated {len(groups)} groups.")
        
        # 2. Migrate Blacklist
        logger.info("Migrating Blacklist...")
        blacklist = local.load_blacklist()
        if blacklist:
            mongo.save_blacklist(blacklist)
            logger.info(f"Successfully migrated {len(blacklist)} blacklist keywords.")
            
        # 3. Migrate Approved Shipments
        logger.info("Migrating Approved Shipments...")
        approved = local.load_approved_records()
        if approved:
            # MongoDB might crash with too large payload, but insert_many handles it usually.
            # We add approved_at if missing
            for rec in approved:
                if 'approved_at' not in rec:
                    rec['approved_at'] = datetime.now().isoformat()
            mongo.shipments.insert_many(approved)
            logger.info(f"Successfully migrated {len(approved)} approved records.")

        # 4. Migrate Inbox (Unprocessed)
        logger.info("Migrating Inbox...")
        inbox_raw = local.load_unprocessed_messages(filter_today=False)
        if inbox_raw:
            mongo.save_unprocessed_messages(inbox_raw)
            logger.info(f"Successfully migrated {len(inbox_raw)} inbox messages.")

        # 5. Migrate Processed Hashes
        logger.info("Migrating Processed Hashes...")
        hashes = local.load_processed_content_hashes()
        if hashes:
            ops = []
            for h, iso_ts in hashes.items():
                try:
                    ts = datetime.fromisoformat(iso_ts)
                except:
                    ts = datetime.now()
                mongo.mark_content_as_processed(h)
            logger.info(f"Successfully migrated {len(hashes)} processed hashes.")

        # 6. Migrate Cargo Types & Config
        logger.info("Migrating Configuration (Cargo Types)...")
        cargo_types = local.load_yuk_tipleri()
        if cargo_types:
            mongo.save_config('cargo_types', cargo_types)
        
        arac_kasa = local.load_arac_kasa_tipleri()
        if arac_kasa:
            mongo.save_config('arac_kasa_tipleri', arac_kasa)
            
        logger.info("Migration COMPLETED successfully.")

    except Exception as e:
        logger.error(f"Migration FAILED: {e}", exc_info=True)

if __name__ == "__main__":
    migrate()
