import sys
import os
import unittest
import json
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mock production_parser BEFORE importing anything
sys.modules['production_parser'] = MagicMock()

from src.services.data_service import DataService
from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

class TestAggressiveDuplicateRemoval(unittest.TestCase):
    def setUp(self):
        self.test_dir = os.path.join(PROJECT_ROOT, 'tests', 'temp_data')
        os.makedirs(self.test_dir, exist_ok=True)
        
        # Patch DataService to use our test directory
        self.data_service = DataService(PROJECT_ROOT)
        self.data_service.onaylanmamis_file = os.path.join(self.test_dir, 'test_onaylanmamis.json')
        
        # Ensure file is clean
        if os.path.exists(self.data_service.onaylanmamis_file):
            os.remove(self.data_service.onaylanmamis_file)
            
        # Mock Orchestrator to use our data_service
        with patch.object(OrchestratorSDK, '_start_background_worker'):
            self.orchestrator = OrchestratorSDK()
            self.orchestrator.data_service = self.data_service
            self.orchestrator.save_lock = MagicMock() # Mock the lock

    def tearDown(self):
        import shutil
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_aggressive_removal(self):
        # 1. Create an existing shipment in the file
        existing_ts = time.time() - 300 # 5 minutes ago
        existing_msg = {
            'message_id': 'old_msg_1',
            'message_timestamp': existing_ts,
            'shipments': [
                {
                    'nereden_il': 'ISTANBUL', 'nereden_ilce': 'PENDIK',
                    'nereye_il': 'ANKARA', 'nereye_ilce': 'CANKAYA',
                    'telefon': '05321234567',
                    'arac_tipi': ['1360'], 'kasa_tipi': ['ACIK'], 'yuk_tipi': ['KOMPLE']
                }
            ],
            'total_shipments': 1
        }
        with open(self.data_service.onaylanmamis_file, 'w', encoding='utf-8') as f:
            json.dump([existing_msg], f)

        # 2. Try to save a new duplicate shipment
        new_res = {
            'status': 'success',
            'msg_id': 'new_msg_2',
            'timestamp': datetime.now().isoformat(),
            'original_msg': {
                'id': 'new_msg_2',
                'body': 'test body',
                'timestamp': time.time(),
                'from': '905321234567@s.whatsapp.net'
            },
            'shipments': [
                {
                    'nereden_il': 'ISTANBUL', 'nereden_ilce': 'PENDIK',
                    'nereye_il': 'ANKARA', 'nereye_ilce': 'CANKAYA',
                    'telefon': '05321234567',
                    'arac_tipi': ['1360'], 'kasa_tipi': ['ACIK'], 'yuk_tipi': ['KOMPLE']
                }
            ]
        }
        
        # Trigger save_results
        self.orchestrator.save_results([new_res])
        
        # 3. VERIFY:
        # Load the file again
        with open(self.data_service.onaylanmamis_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        # There should be 2 message entries (the old shell and the new shell)
        self.assertEqual(len(data), 2)
        
        # Both should have 0 shipments (or status 'duplicate')
        for entry in data:
            self.assertEqual(len(entry.get('shipments', [])), 0)
            if entry['message_id'] == 'old_msg_1':
                self.assertEqual(entry.get('status'), 'duplicate')

if __name__ == '__main__':
    unittest.main()
