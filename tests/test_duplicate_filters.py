import pytest
import os
import json
import shutil
import tempfile
from datetime import datetime
from src.services.data_service import DataService
from tools.submit_approved_loads import YukBuradaSubmitter

class TestDuplicateFilters:
    @pytest.fixture(autouse=True)
    def setup_and_teardown(self):
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Setup test file paths
        self.unapproved_file = os.path.join(self.test_dir, "unapproved.json")
        self.approved_file = os.path.join(self.test_dir, "approved.json")
        self.processed_contents_file = os.path.join(self.test_dir, "processed_contents.json")
        self.blacklist_file = os.path.join(self.test_dir, "blacklist.json")
        self.handled_ids_file = os.path.join(self.test_dir, "handled_ids.json")
        
        # Initialize DataService with test paths
        self.data_service = DataService(self.test_dir)
        self.data_service.onaylanmamis_file = self.unapproved_file
        self.data_service.onaylananlar_file = self.approved_file
        self.data_service.processed_contents_file = self.processed_contents_file
        self.data_service.blacklist_file = self.blacklist_file
        self.data_service.handled_ids_file = self.handled_ids_file
        
        yield
        
        # Cleanup temp directory
        shutil.rmtree(self.test_dir)

    def test_strict_body_duplicates(self):
        """Verify that only 100% strict matching works for message known check."""
        body1 = "Kayseri Ankara 13.60 TIR"
        body2 = "Kayseri Ankara 1360 TIR" # Similar but different (non-strict match, fuzzy matches would be equal)
        body3 = "Kayseri Ankara 13.60 TIR" # Strict match
        
        # Initial: neither is known
        assert not self.data_service.is_body_known(body1)
        assert not self.data_service.is_body_known(body2)
        
        # Mark body1 as processed (saves strict hash)
        self.data_service.mark_content_as_processed(body1)
        
        # Wait for the background save to complete
        from src.services.persistence_manager import persistence_manager
        persistence_manager.write_queue.join()
        
        # body1 (strict match) should be known
        assert self.data_service.is_body_known(body1)
        assert self.data_service.is_body_known(body3)
        
        # body2 (different strictly but same fuzzy) should NOT be known (strict check works!)
        assert not self.data_service.is_body_known(body2)

    def test_is_shipment_approved_and_unapproved(self):
        """Verify is_shipment_approved and is_shipment_unapproved works correctly."""
        shipment = {
            "nereden_il": "ANKARA",
            "nereden_ilce": "CANKAYA",
            "nereye_il": "ISTANBUL",
            "nereye_ilce": "KADIKOY",
            "telefon": "05321112233",
            "arac_tipi": ["Tir"],
            "kasa_tipi": ["Acik"],
            "yuk_tipi": ["Komple"]
        }
        
        # Initially not approved or unapproved
        assert not self.data_service.is_shipment_approved(shipment)
        assert not self.data_service.is_shipment_unapproved(shipment)
        assert not self.data_service.is_shipment_duplicate(shipment)
        
        # Save to unapproved (as message wrapper format)
        now_ts = datetime.now().timestamp()
        unapproved_data = [{
            "message_id": "test_msg_1",
            "message_timestamp": now_ts,
            "shipments": [shipment]
        }]
        with open(self.unapproved_file, 'w', encoding='utf-8') as f:
            json.dump(unapproved_data, f)
            
        # Should be unapproved but not approved
        assert self.data_service.is_shipment_unapproved(shipment)
        assert not self.data_service.is_shipment_approved(shipment)
        assert self.data_service.is_shipment_duplicate(shipment)
        
        # Clear unapproved, save to approved list
        with open(self.unapproved_file, 'w', encoding='utf-8') as f:
            json.dump([], f)
            
        approved_shipment = shipment.copy()
        approved_shipment["createdAt"] = now_ts
        approved_data = [approved_shipment]
        with open(self.approved_file, 'w', encoding='utf-8') as f:
            json.dump(approved_data, f)
            
        # Should be approved but not unapproved
        assert not self.data_service.is_shipment_unapproved(shipment)
        assert self.data_service.is_shipment_approved(shipment)
        assert self.data_service.is_shipment_duplicate(shipment)

    def test_filter_already_submitted(self):
        """Verify _filter_already_submitted handles flat and nested payloads correctly."""
        submitter = YukBuradaSubmitter()
        
        # Set up a temporary gonderilmis_kayitlar.json file
        submitted_file = os.path.join(self.test_dir, "gonderilmis_kayitlar.json")
        
        # Inject custom path into _filter_already_submitted internally
        # We will mock the open call or temporarily patch the file location
        # Since we modified submit_approved_loads to check both 'gonderilmis_kayitlar.json' and 'src/...'
        # We can temporarily patch the class or write in 'gonderilmis_kayitlar.json' of local directory (which is self.test_dir)
        old_cwd = os.getcwd()
        os.chdir(self.test_dir)
        
        try:
            submitted_data = [
                # Nested payload format
                {
                    "id": "KAYSERI_MARDIN_1",
                    "payload": {
                        "pickupCity": "KAYSERI",
                        "destinations": [{"deliveryCity": "MARDIN"}]
                    }
                },
                # Flat payload format (which failed previously)
                {
                    "id": "GAZIANTEP_ERZURUM_1",
                    "payload": {
                        "pickupCity": "GAZIANTEP",
                        "deliveryCity": "ERZURUM"
                    }
                }
            ]
            
            with open("gonderilmis_kayitlar.json", 'w', encoding='utf-8') as f:
                json.dump(submitted_data, f)
                
            records_to_check = [
                # Case 1: Already submitted (Nested)
                {"nereden_il": "KAYSERI", "nereye_il": "MARDIN"},
                # Case 2: Already submitted (Flat)
                {"nereden_il": "GAZIANTEP", "nereye_il": "ERZURUM"},
                # Case 3: New shipment (Not submitted)
                {"nereden_il": "ANKARA", "nereye_il": "ISTANBUL"}
            ]
            
            filtered = submitter._filter_already_submitted(records_to_check)
            
            # Should filter out Cases 1 and 2, leaving only Case 3
            assert len(filtered) == 1
            assert filtered[0]["nereden_il"] == "ANKARA"
            assert filtered[0]["nereye_il"] == "ISTANBUL"
            
        finally:
            os.chdir(old_cwd)
