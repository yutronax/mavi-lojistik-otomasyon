#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for dedup active_ids fix.

Acceptance Criteria:
1. [Critical] Sadece ilçe dolu sevkiyat (nereden_il/nereye_il boş) → save_payload'a eklenir, mark_id_handled çağrılır.
2. [Critical] Herhangi bir işlem sonrasında active_ids'ten çıkarma, mark_id_handled çağrıldıktan SONRA yapılmalı.
3. [High] process_message_task exception fırlatırsa, _task_wrapper'ın except bloğu mark_id_handled YİNE DE çağırmalı.
4. [High] Mesaj active_ids içindeyken kuyruğa eklenmemeli (mevcut davranış, regresyon testi).
5. [Medium] Mesaj body'si mükerrer ise kuyruğa eklenmemeli (mevcut davranış, regresyon testi).

Implementation Plan (henüz yapılmadı):
1. save_results'taki has_valid_shipment kontrolü genişletilecek:
   if s.get('nereden_il') or s.get('nereden_ilce') or s.get('nereye_il') or s.get('nereye_ilce'):
2. _task_wrapper'ın except bloğuna mark_id_handled çağrısı eklenecek.

Test Tekniği:
- OrchestratorSDK.__new__() ile __init__ atla (ağır bağımlılıkları atlama).
- Sadece gerekli attribute'ları manuel ata: active_ids, active_lock, active_body_hashes, data_service, save_lock, processing_queue.
- load_json_safe, save_json_safe gibi dosya işlemlerini mock'la.
- process_message_task'ı doğrudan çağır veya mock'la.
"""

import pytest
import os
import sys
import threading
import json
from unittest.mock import MagicMock, patch, call, Mock
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out problematic imports BEFORE importing OrchestratorSDK
_mock = MagicMock()
sys.modules['google.genai'] = _mock
sys.modules['google'] = _mock
sys.modules['dotenv'] = _mock

# MongoDB mocks (more complex)
_pymongo_mock = MagicMock()
_pymongo_mock.MongoClient = MagicMock()
_pymongo_mock.UpdateOne = MagicMock()
_pymongo_mock.DESCENDING = MagicMock()
_pymongo_errors_mock = MagicMock()
_pymongo_mock.errors = _pymongo_errors_mock
sys.modules['pymongo'] = _pymongo_mock
sys.modules['pymongo.errors'] = _pymongo_errors_mock

from src.parsers.veri_cekici_ayristirici import OrchestratorSDK


def make_orchestrator():
    """
    __init__'i atlayarak, sadece gerekli attribute'ları manuel kuran hafif bir instance.
    Bu, ağır bağımlılıkları (mongo_service, producer_parser, vs.) atlayarak test yapmayı sağlar.
    """
    orch = OrchestratorSDK.__new__(OrchestratorSDK)
    orch.active_ids = set()
    orch.active_lock = threading.Lock()
    orch.active_body_hashes = set()
    orch.data_service = MagicMock()
    orch.data_service._normalize_and_hash = lambda body: f"hash_{body}"
    orch.data_service.mark_id_handled = MagicMock()
    orch.save_lock = threading.Lock()
    orch.processing_queue = MagicMock()
    orch.processing_queue.task_done = MagicMock()
    orch.mongo_service = None  # Oto-onay feature'ını devre dışı bırak
    orch.submitter = None
    return orch


class TestAC1_OnlyIlceShipmentSaved:
    """
    AC-1: Sadece ilçe dolu sevkiyat (nereden_il/nereye_il boş, nereden_ilce/nereye_ilce dolu)
    → save_payload'a eklenir, mark_id_handled çağrılır.
    """

    def test_ilce_only_shipment_saved_and_handled(self):
        """
        Given: process_message_task status='success' döner, shipment sadece ilçe alanlarına sahip
        When: save_results çağrılırsa
        Then: shipment save_payload'a eklenir, mark_id_handled çağrılır
        """
        orch = make_orchestrator()
        msg_id = "msg_ilce_only"

        # Sadece ilçe alanları dolu sevkiyat (İL boş)
        shipment = {
            "id": "ship_001",
            "nereden_il": "",  # BOŞŞ
            "nereden_ilce": "ÇANKIRI",  # DOLU
            "nereye_il": "",  # BOŞŞ
            "nereye_ilce": "ANKARA",  # DOLU
            "arac_tipi": ["1360"],
            "kasa_tipi": ["AÇIK"],
        }

        result = {
            'status': 'success',
            'msg_id': msg_id,
            'original_msg': {
                'id': msg_id,
                'body': 'Test mesaj',
                'timestamp': '1630000000',
                'sender_name': 'Test',
                'from': '1234567890',
                'chat_id': 'chat_1',
                'chat_name': 'Test Chat'
            },
            'shipments': [shipment],
            'timestamp': '2026-08-31T10:00:00',
            'confidence_score': 0.9,
            'confidence_issues': [],
            'invalid_location': False
        }

        with patch('src.parsers.veri_cekici_ayristirici.load_json_safe', return_value=[]):
            with patch('src.parsers.veri_cekici_ayristirici.save_json_safe'):
                with patch('src.parsers.veri_cekici_ayristirici.PROCESSED_FILE', '/tmp/test.json'):
                    orch.data_service.is_shipment_approved = MagicMock(return_value=False)
                    orch.data_service.is_shipment_unapproved = MagicMock(return_value=False)
                    orch.data_service.save_unprocessed_messages = MagicMock(return_value=True)
                    orch.data_service.mark_content_as_processed = MagicMock()
                    orch.data_service.append_unprocessed_log = MagicMock()

                    # save_results çağrı
                    orch.save_results([result])

                    # Kontrol: mark_id_handled çağrılmış olmalı
                    orch.data_service.mark_id_handled.assert_called_with(msg_id)
                    # Kontrol: save_unprocessed_messages çağrılmış olmalı
                    orch.data_service.save_unprocessed_messages.assert_called_once()

                    # Kaydedilen payload'ı kontrol et
                    call_args = orch.data_service.save_unprocessed_messages.call_args
                    save_payload = call_args[0][0]
                    assert msg_id in save_payload, f"Message {msg_id} save_payload'a eklenmemeli"
                    entry = save_payload[msg_id]
                    assert len(entry.get('shipments', [])) == 1


class TestAC2_ActiveIdsRemovedAfterMark:
    """
    AC-2: Herhangi bir işlem sonrasında active_ids'ten çıkarma, mark_id_handled SONRASINDA yapılmalı.

    Mevcut kodda (HATA):
    - save_results içinde mark_id_handled çağrılır, SONRA active_ids çıkarılır
    - Ama _task_wrapper'da finally ÖNCE active_ids çıkarılıyor!

    Testler, ideal durumu (code-copilot implementasyonu sonrası) kontrol eder.
    """

    def test_task_wrapper_active_ids_removed_after_save_results(self):
        """
        Given: _task_wrapper çağrıldı, process_message_task başarılı sonuç döndü
        When: _task_wrapper tam olarak çalışırsa (process_message_task + save_results + finally)
        Then: mark_id_handled çağrıldığı ANDA msg_id hâlâ active_ids'te olmalı
              (henüz finally çalışmadı), _task_wrapper TAMAMLANDIKTAN SONRA ise
              msg_id active_ids'ten çıkarılmış olmalı.

        Sırası (ideal): process_message_task → save_results → mark_id_handled → active_ids.remove (finally'de)
        """
        orch = make_orchestrator()
        msg_id = "msg_order_test"
        api_key = "test_key"
        msg = {
            'id': msg_id,
            'body': 'Test mesaj',
            'timestamp': '1630000000',
            'sender_name': 'Test',
            'from': '1234567890',
            'chat_id': 'chat_1',
            'chat_name': 'Test Chat'
        }

        # Başlangıçta active_ids'e ekle
        with orch.active_lock:
            orch.active_ids.add(msg_id)

        assert msg_id in orch.active_ids, "Message ID active_ids'te olmalı"

        # Mock process_message_task
        success_result = {
            'status': 'success',
            'msg_id': msg_id,
            'original_msg': msg,
            'shipments': [
                {
                    "id": "ship_001",
                    "nereden_il": "ANKARA",
                    "nereye_il": "İSTANBUL",
                    "arac_tipi": [],
                    "kasa_tipi": [],
                }
            ],
            'timestamp': '2026-08-31T10:00:00',
            'confidence_score': 0.9,
            'confidence_issues': [],
            'invalid_location': False
        }

        # mark_id_handled çağrıldığı ANDAKİ active_ids durumunu kaydet
        active_ids_at_mark_time = []

        def track_mark_id_handled(mid):
            active_ids_at_mark_time.append(mid in orch.active_ids)

        orch.data_service.mark_id_handled = Mock(side_effect=track_mark_id_handled)

        with patch.object(orch, 'process_message_task', return_value=success_result):
            with patch('src.parsers.veri_cekici_ayristirici.load_json_safe', return_value=[]):
                with patch('src.parsers.veri_cekici_ayristirici.save_json_safe'):
                    with patch('src.parsers.veri_cekici_ayristirici.PROCESSED_FILE', '/tmp/test.json'):
                        orch.data_service.is_shipment_approved = MagicMock(return_value=False)
                        orch.data_service.is_shipment_unapproved = MagicMock(return_value=False)
                        orch.data_service.save_unprocessed_messages = MagicMock(return_value=True)
                        orch.data_service.mark_content_as_processed = MagicMock()
                        orch.data_service.append_unprocessed_log = MagicMock()

                        # TAM _task_wrapper akışını çalıştır (process_message_task + save_results + finally)
                        orch._task_wrapper(msg, api_key)

        # Kontrol 1: mark_id_handled çağrılmış olmalı
        orch.data_service.mark_id_handled.assert_called_with(msg_id)

        # Kontrol 2 (SIRA): mark_id_handled çağrıldığı ANDA msg_id HÂLÂ active_ids'teydi
        # (finally bloğu henüz çalışmamıştı) — bu SIRANIN doğru olduğunu kanıtlar
        assert active_ids_at_mark_time == [True], (
            f"mark_id_handled çağrıldığı anda msg_id active_ids'te OLMALIYDI "
            f"(finally henüz çalışmamış olmalı), got {active_ids_at_mark_time}"
        )

        # Kontrol 3: _task_wrapper TAMAMLANDIKTAN SONRA msg_id active_ids'ten çıkarılmış olmalı
        assert msg_id not in orch.active_ids, (
            "_task_wrapper tamamlandıktan sonra msg_id active_ids'ten çıkarılmış olmalı (finally bloğu)"
        )


class TestAC3_ExceptionHandling:
    """
    AC-3: process_message_task exception fırlatırsa, _task_wrapper'ın except bloğu
    mark_id_handled YİNE DE çağırmalı.
    """

    def test_task_wrapper_calls_mark_on_exception(self):
        """
        Given: process_message_task exception fırlatır
        When: _task_wrapper except bloğu çalışırsa
        Then: mark_id_handled MUTLAKA çağrılmalı (sonsuz loop'tan korunmak için)
        """
        orch = make_orchestrator()
        msg_id = "msg_exception_test"
        msg = {
            'id': msg_id,
            'body': 'Problematik mesaj',
            'timestamp': '1630000000',
            'sender_name': 'Test',
            'from': '1234567890',
            'chat_id': 'chat_1',
            'chat_name': 'Test Chat'
        }
        api_key = "test_key"

        # Başlangıçta active_ids'e ekle
        with orch.active_lock:
            orch.active_ids.add(msg_id)

        # process_message_task exception fırlatır
        with patch.object(orch, 'process_message_task', side_effect=ValueError("Test hatası")):
            with patch.object(orch, 'save_results') as mock_save:
                # _task_wrapper çağrı
                orch._task_wrapper(msg, api_key)

                # Kontrol 1: save_results çağrılmamış (exception kaynağında)
                mock_save.assert_not_called()

                # Kontrol 2: mark_id_handled MUTLAKA çağrılmalı (exception handling'de)
                orch.data_service.mark_id_handled.assert_called_with(msg_id)

                # Kontrol 3: active_ids'ten çıkarılmış olmalı (finally bloğu)
                assert msg_id not in orch.active_ids, "Message ID active_ids'ten çıkmalı (finally'de)"


class TestAC4_RegressionActiveIdsDuplicate:
    """
    AC-4: Mevcut davranış (regresyon testi) - Mesaj active_ids içindeyken
    kuyruğa eklenmemeli.
    """

    def test_message_not_enqueued_if_in_active_ids(self):
        """
        Given: Mesaj hâlâ active_ids'te (işleme devam ediyor)
        When: add_to_processing_queue çağrılırsa
        Then: Mesaj kuyruğa eklenmemeli (duplicate işlemden korunmak için)
        """
        orch = make_orchestrator()
        msg_id = "msg_dup"
        msg = {
            'id': msg_id,
            'body': 'Test',
            'timestamp': '1630000000',
        }

        # Mesajı active_ids'e ekle (hâlâ işleniyor)
        with orch.active_lock:
            orch.active_ids.add(msg_id)

        # Mock get_unprocessed_messages (test için böyle yapalım)
        with patch.object(orch, 'get_unprocessed_messages', return_value=[msg]):
            actual_added = orch.add_to_processing_queue([msg])

            # Mesaj zaten active_ids'te olduğundan, kuyruğa eklenmemeli
            # actual_added == 0 olmalı
            assert actual_added == 0, f"Mesaj active_ids'te iken {actual_added} eklendi, 0 olmalıydı"


class TestAC5_RegressionBodyHashDuplicate:
    """
    AC-5: Mevcut davranış (regresyon testi) - Mesaj body'si mükerrer ise
    kuyruğa eklenmemeli.
    """

    def test_message_not_enqueued_if_body_hash_in_active(self):
        """
        Given: Mesaj body'sinin hash'i active_body_hashes'te (aynı body ile başka mesaj işleniyor)
        When: add_to_processing_queue çağrılırsa
        Then: Mesaj kuyruğa eklenmemeli (mükerrer içerikten korunmak için)
        """
        orch = make_orchestrator()
        msg_id = "msg_body_dup"
        body = "Aynı olan mesaj içeriği"
        body_hash = f"hash_{body}"

        msg = {
            'id': msg_id,
            'body': body,
            'timestamp': '1630000000',
        }

        # Body hash'ini active_body_hashes'e ekle (başka mesaj aynı body ile işleniyor)
        with orch.active_lock:
            orch.active_body_hashes.add(body_hash)

        # add_to_processing_queue çağrı
        actual_added = orch.add_to_processing_queue([msg])

        # Mesaj body mükerrer olduğundan, kuyruğa eklenmemeli
        assert actual_added == 0, f"Mükerrer body {actual_added} kez eklendi, 0 olmalıydı"


class TestIntegrationFlowSaveResultsFlow:
    """
    Entegrasyon testleri - Tam akış.
    """

    def test_save_results_with_valid_cities_only(self):
        """
        Başarılı senaryo: İl bilgisi dolu sevkiyat başarıyla kaydedilir.
        """
        orch = make_orchestrator()
        msg_id = "msg_integration_1"

        result = {
            'status': 'success',
            'msg_id': msg_id,
            'original_msg': {
                'id': msg_id,
                'body': 'Ankara\'dan İstanbul\'a',
                'timestamp': '1630000000',
                'sender_name': 'Şoför Ali',
                'from': '5551234567',
                'chat_id': 'chat_logistics',
                'chat_name': 'Lojistik Grubu'
            },
            'shipments': [
                {
                    "id": "s1",
                    "neroden_il": "ANKARA",
                    "nereye_il": "İSTANBUL",
                    "arac_tipi": ["1360"],
                    "kasa_tipi": ["AÇIK"],
                }
            ],
            'timestamp': '2026-08-31T10:00:00',
            'confidence_score': 0.95,
            'confidence_issues': [],
            'invalid_location': False
        }

        with patch('src.parsers.veri_cekici_ayristirici.load_json_safe', return_value=[]):
            with patch('src.parsers.veri_cekici_ayristirici.save_json_safe') as mock_save:
                with patch('src.parsers.veri_cekici_ayristirici.PROCESSED_FILE', '/tmp/test.json'):
                    orch.data_service.is_shipment_approved = MagicMock(return_value=False)
                    orch.data_service.is_shipment_unapproved = MagicMock(return_value=False)
                    orch.data_service.save_unprocessed_messages = MagicMock(return_value=True)
                    orch.data_service.mark_content_as_processed = MagicMock()
                    orch.data_service.append_unprocessed_log = MagicMock()

                    orch.save_results([result])

                    # save_unprocessed_messages çağrılmış olmalı
                    orch.data_service.save_unprocessed_messages.assert_called_once()
                    # mark_id_handled çağrılmış olmalı
                    orch.data_service.mark_id_handled.assert_called_with(msg_id)

    def test_save_results_error_entry(self):
        """
        Hata senaryosu: Status='error' olan entry'ler de kaydedilir.
        """
        orch = make_orchestrator()
        msg_id = "msg_error"

        result = {
            'status': 'error',
            'msg_id': msg_id,
            'error': 'Parse hatası',
            'original_msg': {
                'id': msg_id,
                'body': 'Geçersiz mesaj',
                'timestamp': '1630000000',
                'sender_name': 'Test',
                'from': '1234567890',
                'chat_id': 'chat_1',
                'chat_name': 'Test'
            }
        }

        with patch('src.parsers.veri_cekici_ayristirici.load_json_safe', return_value=[]):
            with patch('src.parsers.veri_cekici_ayristirici.save_json_safe'):
                with patch('src.parsers.veri_cekici_ayristirici.PROCESSED_FILE', '/tmp/test.json'):
                    orch.data_service.is_shipment_approved = MagicMock(return_value=False)
                    orch.data_service.is_shipment_unapproved = MagicMock(return_value=False)
                    orch.data_service.save_unprocessed_messages = MagicMock(return_value=True)
                    orch.data_service.mark_content_as_processed = MagicMock()
                    orch.data_service.append_unprocessed_log = MagicMock()

                    orch.save_results([result])

                    # Hata entry'si de kaydedilmeli
                    orch.data_service.save_unprocessed_messages.assert_called_once()
                    call_args = orch.data_service.save_unprocessed_messages.call_args
                    save_payload = call_args[0][0]
                    assert msg_id in save_payload, "Hata entry'si save_payload'a eklenmemeli"
                    assert save_payload[msg_id]['error'] == 'Parse hatası'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
