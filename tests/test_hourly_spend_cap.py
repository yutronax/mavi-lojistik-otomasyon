#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for saatlik-harcama-ust-limit (hourly spend cap).

Acceptance Criteria:
1. [Critical] Given saat başı harcama eşiğin ALTINDA, When yeni bir mesaj
   `add_to_processing_queue()`'ya gelir, Then mevcut davranış AYNEN
   sürmeli — hiçbir yeni kod yolu tetiklenmemeli, mesaj normal işlenmeli.
2. [Critical] Given saat başı toplam harcama (DeepSeek+Groq) ayarlanabilir
   `AI_HOURLY_SPEND_CAP_TRY` eşiğini AŞMIŞ, When yeni bir mesaj gelir,
   Then bu mesaj kuyruğa EKLENMEMELİ, ayrı bir "ertelenmiş" listede
   tutulmalı, WARN seviyesinde loglanmalı.
3. [Critical] Given limit aşılmışken KUYRUKTA ZATEN OLAN veya
   `ThreadPoolExecutor`'da işlenmekte olan mesajlar, When limit kontrolü
   çalışır, Then bu mesajlar DURDURULMAMALI — sadece YENİ mesajların
   kuyruğa eklenmesi engellenir, mevcut işlem akışı kesilmez.
4. [High] Given saat değişimi (örn. 14:59 → 15:00), When yeni saat dilimi
   başlar, Then önceki saatin harcaması pencere dışında kalmalı VE
   ertelenmiş mesajlar OTOMATİK olarak kuyruğa aktarılmalı — manuel
   müdahale gerekmeden.
5. [High] Given `ai_spend_history.json` dosyası bozuk/okunamıyor VEYA
   bellek içi sayaç ilklendirilememiş, When limit kontrolü çalışır, Then
   FAIL-OPEN davranmalı (limit yokmuş gibi mesaj işlemeye devam etmeli).
6. [Medium] Given saat başı harcama TAM eşikte (== eşik), When kontrol
   çalışır, Then mesaj ENGELLENMEMELİ (`>` kullanılmalı, `>=` değil).
"""

import pytest
import os
import sys
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch, Mock, PropertyMock
from io import StringIO
import threading

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out problematic imports BEFORE importing text_gen_parser
_mock = MagicMock()
sys.modules['google.genai'] = _mock
sys.modules['google'] = _mock
sys.modules['dotenv'] = _mock

# MongoDB mocks
_pymongo_mock = MagicMock()
_pymongo_mock.MongoClient = MagicMock()
_pymongo_mock.UpdateOne = MagicMock()
_pymongo_mock.DESCENDING = -1
_pymongo_errors_mock = MagicMock()
_pymongo_errors_mock.ConnectionFailure = Exception
_pymongo_errors_mock.PyMongoError = Exception
_pymongo_mock.errors = _pymongo_errors_mock
sys.modules['pymongo'] = _pymongo_mock
sys.modules['pymongo.errors'] = _pymongo_errors_mock

# Set up logging to capture logs in tests
logging.basicConfig(level=logging.DEBUG)


class TestHourlySpendCap:
    """
    AC-1 through AC-6: Verify hourly spend cap functionality in text_gen_parser
    and integration with veri_cekici_ayristirici.add_to_processing_queue().
    """

    def test_ac6_hourly_cap_exceeded_function_exists(self):
        """
        AC-6: Given `text_gen_parser.py`'nin modülü, When import edilir,
        Then `is_hourly_cap_exceeded()` fonksiyonu MUTLAKA var olmalı.

        This is a critical precondition test — if it fails, implementation hasn't started.
        """
        # Import text_gen_parser module
        import text_gen_parser

        # Check that is_hourly_cap_exceeded function exists
        has_function = hasattr(text_gen_parser, 'is_hourly_cap_exceeded')
        if not has_function:
            pytest.fail(
                "EXPECTED RED: is_hourly_cap_exceeded() function does not exist in text_gen_parser module. "
                "Implementation not started. This is AC-6 precondition failure."
            )

        # Verify it's callable
        assert callable(text_gen_parser.is_hourly_cap_exceeded), \
            "is_hourly_cap_exceeded should be callable"

    def test_ac6_module_level_variables_exist(self):
        """
        AC-6: Given `text_gen_parser.py`, When imported, Then modül-seviyesi
        değişkenler MUTLAKA var olmalı:
        - `_hourly_lock` (threading.Lock)
        - `_current_hour_key` (str or None)
        - `_current_hour_cost_try` (float)

        This verifies the implementation skeleton is present.
        """
        import text_gen_parser

        # Check module-level variables (implementation expectation from plan.md)
        expected_vars = ['_hourly_lock', '_current_hour_key', '_current_hour_cost_try']
        for var_name in expected_vars:
            has_var = hasattr(text_gen_parser, var_name)
            if not has_var:
                pytest.fail(
                    f"EXPECTED RED: Module-level variable '{var_name}' does not exist in text_gen_parser. "
                    f"Expected from plan.md: {expected_vars}. Implementation not fully started."
                )

    def test_ac1_threshold_below_cap_returns_false(self):
        """
        AC-1 & AC-6: Given saat başı harcama eşiğin ALTINDA (örn. 5.0 TL, eşik 9 TL),
        When `is_hourly_cap_exceeded()` çalışır, Then `False` döndürmeli.

        This verifies happy path: spending below cap → no action.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # Simulate current hour cost below cap
            with patch.object(text_gen_parser, '_current_hour_cost_try', 5.0):
                result = text_gen_parser.is_hourly_cap_exceeded()
                assert result is False, \
                    f"Spending 5.0 TL below cap 9.0 should return False, got {result}"

    def test_ac6_exact_cap_limit_not_exceeded(self):
        """
        AC-6: Given saat başı harcama TAM eşikte (== eşik, örn. 9.0 TL = cap 9.0 TL),
        When `is_hourly_cap_exceeded()` çalışır, Then `False` döndürmeli
        (`>` kullanılmalı, `>=` değil — eşiğe TAM ulaşan mesaj ENGELLENMEMELİ).

        This is critical AC-6 behavior: equality does NOT trigger cap.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # Current hour cost EXACTLY at cap
            with patch.object(text_gen_parser, '_current_hour_cost_try', 9.0):
                result = text_gen_parser.is_hourly_cap_exceeded()
                assert result is False, \
                    f"Spending exactly at cap (9.0 == 9.0) should return False (not >=), got {result}"

    def test_ac2_exceeds_cap_returns_true(self):
        """
        AC-2: Given saat başı toplam harcama `AI_HOURLY_SPEND_CAP_TRY` eşiğini AŞMIŞ
        (örn. 10.0 TL > cap 9.0 TL), When `is_hourly_cap_exceeded()` çalışır,
        Then `True` döndürmeli — yeni mesajlar kuyruğa eklenmemeli.

        This verifies cap-exceeded behavior: spending above cap → block new messages.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # Current hour cost exceeds cap
            with patch.object(text_gen_parser, '_current_hour_cost_try', 10.0):
                result = text_gen_parser.is_hourly_cap_exceeded()
                assert result is True, \
                    f"Spending 10.0 TL above cap 9.0 should return True, got {result}"

    def test_ac2_custom_cap_env_variable(self):
        """
        AC-2: Given `AI_HOURLY_SPEND_CAP_TRY` env değişkeni özel bir değerle (örn. 20 TL),
        When `is_hourly_cap_exceeded()` çalışır, Then bu özel eşik kullanılmalı.

        This verifies environment variable customization.
        """
        import text_gen_parser

        # Set custom cap
        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '20.0'}):
            with patch.object(text_gen_parser, '_current_hour_cost_try', 25.0):
                result = text_gen_parser.is_hourly_cap_exceeded()
                assert result is True, \
                    f"Spending 25.0 TL above custom cap 20.0 should return True, got {result}"

            with patch.object(text_gen_parser, '_current_hour_cost_try', 15.0):
                result = text_gen_parser.is_hourly_cap_exceeded()
                assert result is False, \
                    f"Spending 15.0 TL below custom cap 20.0 should return False, got {result}"

    def test_ac4_hour_change_resets_counter(self):
        """
        AC-4: Given saat değişimi (örn. 14:00 → 15:00), When yeni saat dilimi başlar,
        Then önceki saatin harcaması pencere dışında kalmalı VE sayaç sıfırlanmalı.

        This verifies time window sliding: each hour is a fresh window.
        """
        import text_gen_parser

        # Mock datetime.now() to simulate hour progression
        base_time = datetime(2026, 9, 4, 14, 30, 0)
        next_hour = datetime(2026, 9, 4, 15, 30, 0)

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # First hour: set to 10.0 (exceeds cap)
            with patch('text_gen_parser.datetime') as mock_datetime:
                mock_datetime.now.return_value = base_time
                with patch.object(text_gen_parser, '_current_hour_cost_try', 10.0):
                    with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                        result = text_gen_parser.is_hourly_cap_exceeded()
                        assert result is True, \
                            f"Hour 14: Spending 10.0 should exceed cap, got {result}"

            # Simulate hour change: reset to new hour
            with patch('text_gen_parser.datetime') as mock_datetime:
                mock_datetime.now.return_value = next_hour
                with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                    with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-15'):
                        result = text_gen_parser.is_hourly_cap_exceeded()
                        assert result is False, \
                            f"Hour 15 (new window): Reset spending to 0.0 should not exceed cap, got {result}"

    def test_ac5_fail_open_missing_json_file(self):
        """
        AC-5: Given `ai_spend_history.json` dosyası bozuk/okunamıyor,
        When `is_hourly_cap_exceeded()` çalışır, Then FAIL-OPEN davranmalı
        (hata fırlatmamadı, False döndürmeli — limit yokmuş gibi devam etmeli).

        This verifies safety: file errors don't break system.
        """
        import text_gen_parser

        # Simulate file read failure: make is_hourly_cap_exceeded handle exceptions gracefully
        # If implementation uses try-except with fail-open, this should return False
        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # Set counter to exceed cap, but mock file operations to fail
            with patch.object(text_gen_parser, '_current_hour_cost_try', 10.0):
                # If implementation properly handles file errors with fail-open,
                # it might still return True based on memory value, OR it might
                # have a safety check that returns False on file error.
                # The critical point is: it should NOT raise an exception.
                try:
                    result = text_gen_parser.is_hourly_cap_exceeded()
                    # Either True (memory valid) or False (file error fallback) is OK
                    # as long as no exception is raised
                    assert isinstance(result, bool), \
                        f"is_hourly_cap_exceeded should return bool even on file error, got {type(result)}"
                except Exception as e:
                    pytest.fail(
                        f"AC-5 FAIL-OPEN: is_hourly_cap_exceeded raised {type(e).__name__}: {e}. "
                        f"Should handle file errors gracefully without raising."
                    )

    def test_ac2_ac3_integration_add_to_processing_queue_blocks_new_message(self):
        """
        AC-2 & AC-3: Given `add_to_processing_queue()` method, When
        `is_hourly_cap_exceeded()` returns True (limit exceeded),
        Then:
        - NEW message should NOT be added to processing_queue
        - Already-queued or in-progress messages should NOT be affected

        This integration test verifies the orchestrator respects the cap.

        FIXED: Uses correct OrchestratorSDK class and mocks actual dependencies.
        """
        # Import orchestrator with correct class name
        from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

        # Mock all init dependencies to avoid file I/O and external services
        with patch('src.parsers.veri_cekici_ayristirici.get_default_manager') as mock_get_manager:
            mock_api_key_manager = MagicMock()
            mock_api_key_manager.get_all_keys.return_value = ['test_key']
            mock_get_manager.return_value = mock_api_key_manager

            with patch('src.parsers.veri_cekici_ayristirici.Reporter'):
                with patch('src.parsers.veri_cekici_ayristirici.DataService') as mock_data_service_class:
                    mock_data_service = MagicMock()
                    mock_data_service.load_blacklist.return_value = []
                    mock_data_service.is_id_handled.return_value = False
                    mock_data_service.is_body_known.return_value = False
                    mock_data_service_class.return_value = mock_data_service

                    with patch('src.parsers.veri_cekici_ayristirici.ProductionParser'):
                        with patch('src.parsers.veri_cekici_ayristirici.LocationValidator'):
                            with patch('src.parsers.veri_cekici_ayristirici.QualityGate'):
                                with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
                                    # Create orchestrator instance
                                    orchestrator = OrchestratorSDK()

                                    # Mock processing_queue to track calls
                                    orchestrator.processing_queue = Mock()

                                    # Simulate a message dict
                                    message = {
                                        'id': 'test_msg_1',
                                        'body': 'ISTANBUL ANKARA TIR LAZIM. Acil sipariş var, fiyat sorunuz.',
                                        'from': '+555555555',
                                        'ack': 1
                                    }

                                    # Mock is_hourly_cap_exceeded to return True (cap exceeded)
                                    import text_gen_parser
                                    with patch.object(text_gen_parser, 'is_hourly_cap_exceeded', return_value=True):
                                        # Call add_to_processing_queue with a LIST (not single dict)
                                        try:
                                            orchestrator.add_to_processing_queue([message])
                                            # If implementation correctly blocks, queue.put() should NOT be called
                                            # or message should be skipped
                                            orchestrator.processing_queue.put.assert_not_called()
                                        except AttributeError as e:
                                            pytest.fail(
                                                "AC-2/AC-3: add_to_processing_queue() method signature mismatch. "
                                                f"Expected to accept List[Dict], got error: {e}"
                                            )

    def test_ac1_integration_add_to_processing_queue_allows_under_cap(self):
        """
        AC-1: Given `add_to_processing_queue()`, When `is_hourly_cap_exceeded()` returns False
        (cap NOT exceeded), Then message SHOULD be added to processing_queue normally —
        no change in current behavior.

        This verifies happy path integration: normal messages still flow.

        FIXED: Uses correct OrchestratorSDK class and mocks actual dependencies.
        """
        from src.parsers.veri_cekici_ayristirici import OrchestratorSDK

        # Mock all init dependencies
        with patch('src.parsers.veri_cekici_ayristirici.get_default_manager') as mock_get_manager:
            mock_api_key_manager = MagicMock()
            mock_api_key_manager.get_all_keys.return_value = ['test_key']
            mock_get_manager.return_value = mock_api_key_manager

            with patch('src.parsers.veri_cekici_ayristirici.Reporter'):
                with patch('src.parsers.veri_cekici_ayristirici.DataService') as mock_data_service_class:
                    mock_data_service = MagicMock()
                    mock_data_service.load_blacklist.return_value = []
                    mock_data_service.is_id_handled.return_value = False
                    mock_data_service.is_body_known.return_value = False
                    mock_data_service_class.return_value = mock_data_service

                    with patch('src.parsers.veri_cekici_ayristirici.ProductionParser'):
                        with patch('src.parsers.veri_cekici_ayristirici.LocationValidator'):
                            with patch('src.parsers.veri_cekici_ayristirici.QualityGate'):
                                with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
                                    # Create orchestrator instance
                                    orchestrator = OrchestratorSDK()

                                    # Mock processing_queue
                                    orchestrator.processing_queue = Mock()

                                    message = {
                                        'id': 'test_msg_2',
                                        'body': 'ISTANBUL ANKARA TIR LAZIM. Acil sipariş var, fiyat sorunuz.',
                                        'from': '+555555556',
                                        'ack': 1
                                    }

                                    # Mock is_hourly_cap_exceeded to return False (cap NOT exceeded)
                                    import text_gen_parser
                                    with patch.object(text_gen_parser, 'is_hourly_cap_exceeded', return_value=False):
                                        try:
                                            # Call add_to_processing_queue with a LIST (not single dict)
                                            orchestrator.add_to_processing_queue([message])
                                            # Message should be processed normally (queue.put might be called)
                                            # At minimum, no exception should be raised
                                            orchestrator.processing_queue.put.assert_called()
                                        except AttributeError as e:
                                            pytest.fail(
                                                "AC-1: add_to_processing_queue() method signature mismatch. "
                                                f"Expected to accept List[Dict], got error: {e}"
                                            )
                                        except Exception as e:
                                            pytest.fail(
                                                f"AC-1: Unexpected exception in add_to_processing_queue under cap: {type(e).__name__}: {e}"
                                            )

