#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for Onaylananlar.json cache optimization (AC#1-6).

CRITICAL: These tests expect _approved_cache, _load_approved(), _save_approved()
to be implemented per _unprocessed_cache pattern (lines 306-338 of admin_panel.py).

Currently (without cache impl), tests will RED with:
  - json.load() count assertions FAIL (file is re-read)
  - Missing functions will trigger AttributeError

After implementation, all AC-critical assertions will PASS.

Test strategy:
  - Mock APPROVED_PATH to temp file (never touch real 143MB Onaylananlar.json)
  - Call _approve_message() directly (no Flask HTTP layer needed)
  - Track json.load() and _atomic_write() counts to verify cache usage
"""

import pytest
import json
import os
import sys
import tempfile
import time
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import src.api.admin_panel as admin_panel


def track_json_load_count():
    """Helper: Return (tracked_json_load_func, call_count_list)."""
    count = [0]
    original = json.load

    def tracked(fp, *args, **kwargs):
        count[0] += 1
        return original(fp, *args, **kwargs)

    return tracked, count


def track_atomic_write_calls():
    """Helper: Return (tracked_atomic_write_func, calls_list)."""
    calls = []

    def tracked(path, content):
        calls.append({'path': path, 'content': content})
        # Actually write to make files exist for read-back
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

    return tracked, calls


@pytest.fixture(autouse=True)
def _reset_approved_cache():
    """Her testten önce/sonra admin_panel'in global cache state'ini sıfırlar
    (test izolasyonu için — modül-seviyesi global cache birden fazla test
    arasında paylaşıldığı için gerekli)."""
    admin_panel._approved_cache = []
    admin_panel._approved_cache_loaded = False
    yield
    admin_panel._approved_cache = []
    admin_panel._approved_cache_loaded = False


# ===================== AC-1: Single approval =====================

class TestAC1SingleApproval:
    """AC-1 [Critical]: Single approval appends to cache; NO full file re-read."""

    def test_ac1_no_json_load_on_approval(self):
        """
        AC-1 critical assertion:
          - Cache impl expected: json.load() = 0 (cache used, no file read)
          - Current (no cache): json.load() >= 1 (full file re-read)

        TEST SHOULD FAIL (RED) until _approved_cache implemented.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            with open(approved_file, "w", encoding="utf-8") as f:
                json.dump([{"id": 0}], f)

            # Cache'i önceden ısıt (gerçek senaryo: bu, sürecin İLK onayı
            # değil — daha önceki bir onay/erişim zaten cache'i doldurmuş
            # olurdu; AC-1 "TEKRAR okuma yok" der, "hiç okuma yok" demez)
            with patch("src.api.admin_panel.APPROVED_PATH", approved_file):
                admin_panel._load_approved()

            mock_shipment = {"id": 1, "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": "AÇIK", "kasa_tipi": []}
            mock_msg = {"message_id": "msg_ac1", "shipments": [mock_shipment], "message_info": {"body": "Test"}}

            tracked_json_load, json_load_count = track_json_load_count()
            tracked_atomic_write, atomic_calls = track_atomic_write_calls()

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", return_value=[mock_msg]), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("json.load", side_effect=tracked_json_load), \
                 patch("src.api.admin_panel._atomic_write", side_effect=tracked_atomic_write):

                with admin_panel.app.test_request_context():
                    # Call approval directly (not via Flask)
                    # unprocessed_approve internally: reads approved file, appends, writes
                    # Expected: with cache, no json.load. Without cache: json.load >= 1
                    admin_panel.unprocessed_approve.__wrapped__("msg_ac1", 0)

                # AC-1 CRITICAL ASSERTION
                assert json_load_count[0] == 0, \
                    f"AC-1 FAILED: json.load() called {json_load_count[0]} times AFTER cache warm-up. " \
                    f"Expected 0 (cache impl, no disk read on subsequent approval). " \
                    f"Current code re-reads full file. Implement _load_approved()/_save_approved()."


# ===================== AC-2: Bulk approval =====================

class TestAC2BulkApproval:
    """AC-2 [Critical]: Bulk approval — all valid shipments in ONE cache update + ONE disk write."""

    def test_ac2_no_json_load_bulk(self):
        """
        AC-2 critical assertion:
          - Cache impl expected: json.load() = 0 (cache used)
          - Current (no cache): json.load() >= 1 (file read once)

        TEST SHOULD FAIL (RED) until _approved_cache implemented.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            with open(approved_file, "w", encoding="utf-8") as f:
                json.dump([], f)

            # Cache'i önceden ısıt (gerçek senaryo: bu, sürecin İLK onayı
            # değil — daha önceki bir onay/erişim zaten cache'i doldurmuş
            # olurdu; AC-2 "TEKRAR okuma yok" der, "hiç okuma yok" demez)
            with patch("src.api.admin_panel.APPROVED_PATH", approved_file):
                admin_panel._load_approved()

            shipments = [
                {"id": 1, "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": "AÇIK", "kasa_tipi": []},
                {"id": 2, "nereden_il": "İZMİR", "nereye_il": "BURSA", "arac_tipi": "AÇIK", "kasa_tipi": []},
                {"id": 3, "nereden_il": "BURSA", "nereye_il": "GAZİANTEP", "arac_tipi": "AÇIK", "kasa_tipi": []},
            ]
            mock_msg = {"message_id": "msg_ac2", "shipments": shipments, "message_info": {"body": "Bulk"}}

            tracked_json_load, json_load_count = track_json_load_count()
            tracked_atomic_write, atomic_calls = track_atomic_write_calls()

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", return_value=[mock_msg]), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("json.load", side_effect=tracked_json_load), \
                 patch("src.api.admin_panel._atomic_write", side_effect=tracked_atomic_write):

                count, err = admin_panel._approve_message("msg_ac2")

                # Verify all 3 approved
                assert count == 3 and err is None, f"Expected count=3, err=None; got count={count}, err={err}"

                # AC-2 CRITICAL ASSERTION
                assert json_load_count[0] == 0, \
                    f"AC-2 FAILED: json.load() called {json_load_count[0]} times AFTER cache warm-up. " \
                    f"Expected 0 (cache impl, no file read on subsequent approval). " \
                    f"All shipments should be appended to cache in ONE update, ONE disk write."

    def test_ac2_count_returned_correctly(self):
        """
        AC-2: Verify count return value is correct.
        This test verifies _approve_message logic independently of cache.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            with open(approved_file, "w", encoding="utf-8") as f:
                json.dump([], f)

            shipments = [
                {"id": 1, "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": "AÇIK", "kasa_tipi": []},
                {"id": 2, "nereden_il": "İZMİR", "nereye_il": "BURSA", "arac_tipi": "AÇIK", "kasa_tipi": []},
            ]
            mock_msg = {"message_id": "msg_count", "shipments": shipments, "message_info": {"body": "Count test"}}

            _, atomic_calls = track_atomic_write_calls()

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", return_value=[mock_msg]), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("src.api.admin_panel._atomic_write", side_effect=lambda p, c: atomic_calls.append(c)):

                count, err = admin_panel._approve_message("msg_count")

                # Verify count
                assert count == 2, f"AC-2: Expected count=2, got {count}"
                assert err is None, f"AC-2: Expected err=None, got {err}"


# ===================== AC-3: Lazy load once =====================

class TestAC3LazyLoadOnce:
    """AC-3 [High]: Cache loaded once on first approval; second doesn't re-read file."""

    def test_ac3_second_approval_no_reread(self):
        """
        AC-3 critical assertion:
          - First approval: cache loaded (might call json.load once)
          - Second approval: cache reused (NO additional json.load)
          - Expected total: json.load() = 0 with cache impl, or = 1 on first then 0 on second
          - Current: json.load() >= 2 (each reads file)

        TEST SHOULD FAIL (RED) until _approved_cache + _load_approved() implemented.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            with open(approved_file, "w", encoding="utf-8") as f:
                json.dump([], f)

            msg1 = {"message_id": "msg_3a", "shipments": [{"id": 1, "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": "AÇIK", "kasa_tipi": []}], "message_info": {"body": "First"}}
            msg2 = {"message_id": "msg_3b", "shipments": [{"id": 2, "nereden_il": "BURSA", "nereye_il": "GAZİANTEP", "arac_tipi": "AÇIK", "kasa_tipi": []}], "message_info": {"body": "Second"}}

            tracked_json_load, json_load_count = track_json_load_count()
            tracked_atomic_write, atomic_calls = track_atomic_write_calls()

            # Mock _load_unprocessed to return different messages on each call
            unprocessed_state = [msg1, msg2]
            call_count = [0]

            def mock_load_unprocessed():
                result = unprocessed_state[call_count[0]:]
                call_count[0] += 1
                return result

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", side_effect=mock_load_unprocessed), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("json.load", side_effect=tracked_json_load), \
                 patch("src.api.admin_panel._atomic_write", side_effect=tracked_atomic_write):

                # First approval
                count1, _ = admin_panel._approve_message("msg_3a")
                load_count_after_first = json_load_count[0]

                # Second approval
                count2, _ = admin_panel._approve_message("msg_3b")
                load_count_after_second = json_load_count[0]

                # AC-3 CRITICAL ASSERTION
                additional_loads = load_count_after_second - load_count_after_first
                assert additional_loads == 0, \
                    f"AC-3 FAILED: Second approval caused {additional_loads} additional json.load() calls. " \
                    f"Expected 0 (cache reused). Total: {load_count_after_second}, First: {load_count_after_first}. " \
                    f"IMPLEMENT: Cache should persist across approvals (no lazy reload)."


# ===================== AC-4: Missing file =====================

class TestAC4MissingFile:
    """AC-4 [High]: Missing Onaylananlar.json created atomically, no error."""

    def test_ac4_missing_file_creates_atomically(self):
        """
        AC-4: File doesn't exist; approval should create it via _atomic_write.
        Expected: No exception, _atomic_write called, file created
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            # DO NOT create file

            mock_shipment = {"id": 1, "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": "AÇIK", "kasa_tipi": []}
            mock_msg = {"message_id": "msg_ac4", "shipments": [mock_shipment], "message_info": {"body": "New file"}}

            _, atomic_calls = track_atomic_write_calls()

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", return_value=[mock_msg]), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("src.api.admin_panel._atomic_write", side_effect=lambda p, c: atomic_calls.append((p, c)) or (atomic_calls[-1] and _write_file(p, c))):

                with admin_panel.app.test_request_context():
                    # Should not crash
                    admin_panel.unprocessed_approve.__wrapped__("msg_ac4", 0)

                # File should exist
                assert os.path.exists(approved_file), "AC-4: File should be created"
                with open(approved_file, "r", encoding="utf-8") as f:
                    created = json.load(f)
                assert len(created) == 1, f"AC-4: File should have 1 shipment, got {len(created)}"


def _write_file(path, content):
    """Helper to write file."""
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


# ===================== AC-5: Partial bulk (invalid locations) =====================

class TestAC5PartialBulk:
    """AC-5 [Medium]: Bulk approval skips invalid locations; only valid ones cached."""

    def test_ac5_skip_invalid_location(self):
        """
        AC-5: 3 shipments, 1 invalid (BİLİNMEYEN nereden).
        Expected: count=2 (invalid skipped)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            with open(approved_file, "w", encoding="utf-8") as f:
                json.dump([], f)

            shipments = [
                {"id": 1, "nereden_il": "ANKARA", "nereye_il": "İSTANBUL", "arac_tipi": "AÇIK", "kasa_tipi": []},
                {"id": 2, "nereden_il": "BİLİNMEYEN", "nereye_il": "BURSA", "arac_tipi": "AÇIK", "kasa_tipi": []},  # INVALID
                {"id": 3, "nereden_il": "GAZİANTEP", "nereye_il": "HATAY", "arac_tipi": "AÇIK", "kasa_tipi": []},
            ]
            mock_msg = {"message_id": "msg_ac5", "shipments": shipments, "message_info": {"body": "Mixed"}}

            _, atomic_calls = track_atomic_write_calls()

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", return_value=[mock_msg]), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("src.api.admin_panel._atomic_write", side_effect=lambda p, c: (atomic_calls.append(json.loads(c)), _write_file(p, c))):

                count, err = admin_panel._approve_message("msg_ac5")

                # AC-5: count should be 2 (invalid skipped)
                assert count == 2, f"AC-5 FAILED: Expected count=2, got {count}"
                assert err is None, f"AC-5: err should be None, got {err}"

                # Verify IDs written (should not include id=2)
                if atomic_calls:
                    written = atomic_calls[-1][0] if isinstance(atomic_calls[-1], tuple) else atomic_calls[-1]
                    written_ids = [item["id"] for item in written]
                    assert 2 not in written_ids, f"AC-5: id=2 (invalid) should not be written, got ids {written_ids}"


# ===================== AC-6: No shipments =====================

class TestAC6NoShipments:
    """AC-6 [Medium]: No shipments; no cache/disk write."""

    def test_ac6_empty_shipments_no_write(self):
        """
        AC-6: Message has no shipments.
        Expected: Error (count=0, err="Sevkiyat yok"), NO _atomic_write called
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            with open(approved_file, "w", encoding="utf-8") as f:
                json.dump([], f)

            mock_msg = {"message_id": "msg_ac6", "shipments": [], "message_info": {"body": "Empty"}}

            _, atomic_calls = track_atomic_write_calls()

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", return_value=[mock_msg]), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("src.api.admin_panel._atomic_write", side_effect=lambda p, c: atomic_calls.append(c)):

                count, err = admin_panel._approve_message("msg_ac6")

                # AC-6: count=0, error
                assert count == 0, f"AC-6: Expected count=0, got {count}"
                assert err == "Sevkiyat yok", f"AC-6: Expected err='Sevkiyat yok', got {err}"

                # AC-6 CRITICAL: NO _atomic_write called (no wasted disk I/O)
                assert len(atomic_calls) == 0, \
                    f"AC-6 FAILED: _atomic_write called {len(atomic_calls)} times. " \
                    f"Expected 0 (no shipments, no write)."

    def test_ac6_invalid_location_single_no_write(self):
        """
        AC-6: Single shipment with invalid location.
        Expected: Error (400, "Geçersiz lokasyon"), NO _atomic_write called
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            approved_file = os.path.join(tmpdir, "Onaylananlar.json")
            with open(approved_file, "w", encoding="utf-8") as f:
                json.dump([], f)

            mock_msg = {
                "message_id": "msg_ac6_inv",
                "shipments": [{"id": 1, "nereden_il": "", "nereye_il": "İSTANBUL", "arac_tipi": "AÇIK", "kasa_tipi": []}],
                "message_info": {"body": "Invalid loc"}
            }

            _, atomic_calls = track_atomic_write_calls()

            with patch("src.api.admin_panel.APPROVED_PATH", approved_file), \
                 patch("src.api.admin_panel._load_unprocessed", return_value=[mock_msg]), \
                 patch("src.api.admin_panel._save_unprocessed"), \
                 patch("src.api.admin_panel._submission_queue", None), \
                 patch("src.api.admin_panel._atomic_write", side_effect=lambda p, c: atomic_calls.append(c)):

                with admin_panel.app.test_request_context():
                    # unprocessed_approve should return error
                    result = admin_panel.unprocessed_approve.__wrapped__("msg_ac6_inv", 0)

                # AC-6 CRITICAL: NO _atomic_write called on validation error
                assert len(atomic_calls) == 0, \
                    f"AC-6 FAILED: _atomic_write called {len(atomic_calls)} times on invalid location. " \
                    f"Expected 0 (validation error, no write)."


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
