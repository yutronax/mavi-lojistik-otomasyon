import os
import sys
import time
from datetime import datetime

# Project root for imports
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

def test_id_marking():
    orchestrator = OrchestratorSDK()
    
    # Mock message
    msg_id = f"test_id_{int(time.time())}"
    msg = {
        'id': msg_id,
        'body': 'TEST MESSAGE FOR ID MARKING',
        'from': '1234567890',
        'timestamp': time.time()
    }
    
    print(f"1. Mesaj kuyruğa ekleniyor. ID: {msg_id}")
    orchestrator.add_to_processing_queue([msg])
    
    print("2. ID'nin hemen işaretlenip işaretlenmediği kontrol ediliyor...")
    is_handled = orchestrator.data_service.is_id_handled(msg_id)
    print(f"ID İşaretlendi mi? {'EVET' if is_handled else 'HAYIR'}")
    
    print("\n3. Aynı mesaj tekrar eklenmeye çalışılıyor...")
    added_count = orchestrator.add_to_processing_queue([msg])
    print(f"Tekrar eklenen mesaj sayısı: {added_count} (0 olmalı)")

if __name__ == "__main__":
    test_id_marking()
