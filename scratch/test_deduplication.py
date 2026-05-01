import os
import sys
import time
from datetime import datetime, timedelta

# Project root for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.services.data_service import DataService

def test_deduplication():
    from src.services.persistence_manager import persistence_manager
    ds = DataService(PROJECT_ROOT)
    
    # Clean state for testing (Warning: this affects actual data if run in prod, but it's a scratch script)
    # We'll just use a unique body to be safe
    unique_id = int(time.time())
    test_body = f"TEST MESAJI {unique_id} ADANA MERKEZ 13.60 TIR ACIL"
    
    print(f"1. İlk kez içerik işaretleniyor: {test_body}")
    ds.mark_content_as_processed(test_body)
    
    # Wait for background writer
    persistence_manager.write_queue.join()
    
    # Clear internal caches of DataService to force reload from disk
    ds._content_hashes_cache = None 
    
    print("2. Hemen ardından kontrol ediliyor (Kopya olmalı)...")
    is_known = ds.is_body_known(test_body)
    print(f"Sonuç: {'KOPYA' if is_known else 'YENİ'}")
    
    print("\n3. 100% benzeyen kuralı testi...")
    test_body_exact = test_body # Aynı
    is_known_exact = ds.is_body_known(test_body_exact)
    print(f"Tam eşleşme sonucu: {'KOPYA' if is_known_exact else 'YENİ'}")
    
    print("\n4. Küçük farkla test (Noktalama farkı)...")
    test_body_diff = test_body + "." # Nokta eklendi
    is_known_diff = ds.is_body_known(test_body_diff)
    print(f"Noktalama farkı sonucu (Fuzzy check sayesinde kopya olmalı): {'KOPYA' if is_known_diff else 'YENİ'}")

if __name__ == "__main__":
    test_deduplication()
