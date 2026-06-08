import sys
import os
import unittest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Add project root to sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Mock production_parser BEFORE importing OrchestratorSDK
sys.modules['production_parser'] = MagicMock()
from production_parser import ProductionParser

# Import the class to test
from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

class TestShipmentFiltering(unittest.TestCase):
    def setUp(self):
        # Patching dependencies that we don't want to run during unit tests
        self.patcher1 = patch('src.parsers.veri_cekici_ayristirici.get_default_manager')
        self.patcher2 = patch('src.parsers.veri_cekici_ayristirici.DataService')
        self.patcher3 = patch('src.parsers.veri_cekici_ayristirici.ProductionParser')
        
        self.mock_manager = self.patcher1.start()
        self.mock_data_service = self.patcher2.start()
        self.mock_parser_class = self.patcher3.start()
        
        # Setup mocks
        self.mock_manager.return_value.get_all_keys.return_value = ['test_key']
        self.mock_parser = self.mock_parser_class.return_value
        
        # Initialize Orchestrator
        with patch.object(OrchestratorSDK, '_start_background_worker'):
            self.orchestrator = OrchestratorSDK()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        self.patcher3.stop()

    def test_shipment_filtering(self):
        # Prepare mock shipments
        mock_shipments = [
            # Valid shipment
            {
                'nereden_il': 'ISTANBUL', 'nereden_ilce': 'PENDIK',
                'nereye_il': 'ANKARA', 'nereye_ilce': 'CANKAYA',
                'telefon': '05321234567'
            },
            # International shipment (should be filtered)
            {
                'nereden_il': 'YURT DIŞI', 'nereden_ilce': '',
                'nereye_il': 'ISTANBUL', 'nereye_ilce': 'TUZLA',
                'telefon': '05321234567'
            },
            # Missing origin (should be filtered)
            {
                'nereden_il': '', 'nereden_ilce': '',
                'nereye_il': 'IZMIR', 'nereye_ilce': 'BORNOVA',
                'telefon': '05321234567'
            },
            # Missing destination (should be filtered)
            {
                'nereden_il': 'BURSA', 'nereden_ilce': 'NILUFER',
                'nereye_il': '', 'nereye_ilce': '',
                'telefon': '05321234567'
            }
        ]
        self.mock_parser.parse_message.return_value = mock_shipments
        
        msg = {
            'id': 'test_msg_1',
            'body': 'test body',
            'from': '905321234567@s.whatsapp.net',
            'sender_name': 'Test User'
        }
        
        result = self.orchestrator.process_message_task((msg, 'test_key'))
        
        self.assertEqual(result['status'], 'success')
        self.assertEqual(len(result['shipments']), 1)
        self.assertEqual(result['shipments'][0]['nereden_il'], 'ISTANBUL')
        self.assertEqual(result['shipments'][0]['nereye_il'], 'ANKARA')

    def test_all_filtered(self):
        # Prepare mock shipments (all invalid)
        mock_shipments = [
            {
                'nereden_il': 'YURT DIŞI', 'nereden_ilce': '',
                'nereye_il': 'ISTANBUL', 'nereye_ilce': 'TUZLA',
                'telefon': '05321234567'
            }
        ]
        self.mock_parser.parse_message.return_value = mock_shipments
        
        msg = {
            'id': 'test_msg_2',
            'body': 'test body',
            'from': '905321234567@s.whatsapp.net'
        }
        
        result = self.orchestrator.process_message_task((msg, 'test_key'))
        
        self.assertEqual(result['status'], 'error')
        self.assertIn('All shipments filtered', result['error'])

if __name__ == '__main__':
    unittest.main()
