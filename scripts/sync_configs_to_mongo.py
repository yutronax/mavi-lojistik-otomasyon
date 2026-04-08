import os
import sys
import json

# Add project root to sys.path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

from src.services.mongo_service import MongoDataService
from src.utils.file_ops import safe_json_load

def sync_configs():
    print("Syncing configuration files to MongoDB...")
    mongo = MongoDataService()
    
    data_dir = os.path.join(project_root, 'data')
    
    # 1. araç/kasa tipleri
    arac_kasa_file = os.path.join(data_dir, 'arac_kasa_tipleri.json')
    if os.path.exists(arac_kasa_file):
        data = safe_json_load(arac_kasa_file)
        if data:
            mongo.save_arac_kasa_tipleri(data)
            print(f"Synced {arac_kasa_file}")

    # 2. il/ilçeler
    il_ilceler_file = os.path.join(data_dir, 'il_ilçeler.json')
    if os.path.exists(il_ilceler_file):
        data = safe_json_load(il_ilceler_file)
        if data:
            mongo.save_il_ilceler(data)
            print(f"Synced {il_ilceler_file}")

    # 3. il/ilçe/mahalle (Detaylı)
    il_ilce_mahalle_file = os.path.join(data_dir, 'il_ilçe_mahalle.json')
    if os.path.exists(il_ilce_mahalle_file):
        data = safe_json_load(il_ilce_mahalle_file)
        if data:
            mongo.save_config('il_ilce_mahalle', data)
            print(f"Synced {il_ilce_mahalle_file}")

    # 4. yük tipi
    yuk_tipi_file = os.path.join(data_dir, 'yuk_tipi.json')
    if os.path.exists(yuk_tipi_file):
        data = safe_json_load(yuk_tipi_file)
        if data:
            mongo.save_config('yuk_tipleri', data)
            print(f"Synced {yuk_tipi_file}")

    print("Sync complete.")

if __name__ == "__main__":
    sync_configs()
