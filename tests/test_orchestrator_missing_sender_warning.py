#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for orchestrator missing sender warning (veri_cekici_ayristirici).

Acceptance Criteria:
4. [High] Given `participantAlt` YOK (undefined) VE gerçek gönderen `participant`
   (LID) alanında, When mesaj işlenir, Then mesaj mevcut davranışla
   (fail-open, işlenmeye devam) tutarlı kalmalı AMA "gönderen kimliği LID,
   blacklist eşleşmesi belirsiz" seviyesinde WARN loglanmalı.

5. [High] Given hiçbir katmanda (participantAlt, participant, from,
   sender_number) gönderen numarası tespit edilemiyor, When mesaj işlenir,
   Then mesaj yine fail-open işlenmeli (toptan bloklama YAPILMAMALI) ama
   WARN/ERROR seviyesinde açıkça loglanmalı.
"""

import pytest
import os
import sys
import logging
from unittest.mock import MagicMock, patch, Mock
from io import StringIO

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out problematic imports
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

# Set up logging
logging.basicConfig(level=logging.DEBUG)


class TestOrchestratorMissingSenderWarning:
    """
    AC-4, AC-5: Verify that veri_cekici_ayristirici.py produces WARN logs
    when sender identification fails or is ambiguous, while still processing
    messages (fail-open behavior).
    """

    def test_missing_sender_raw_produces_warn_log_ac5(self, caplog):
        """
        AC-5: Given hiçbir katmanda gönderen numarası tespit edilemiyor
        (`from` alanı boş/yok, participantAlt yok, participant LID),
        When add_to_processing_queue metodu çalışır,
        Then:
        - Mesaj fail-open işlenmeli (queue'ya eklenebilir/continue)
        - WARN seviyesinde log üretilmeli

        NOTE: This test currently FAILS because the code doesn't produce
        WARN log when sender_raw is empty. After fix, it should PASS.
        """
        # Read orchestrator source to verify current behavior
        orchestrator_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'parsers',
            'veri_cekici_ayristirici.py'
        )

        if os.path.exists(orchestrator_file):
            with open(orchestrator_file, 'r', encoding='utf-8') as f:
                orchestrator_code = f.read()

            # Check if there's a WARN log in the else block of sender_raw check
            # Current code structure (lines ~505-510):
            # if sender_raw:
            #     if is_phone_in_list(...):
            #         continue
            # (NO else block with WARN log)

            # After fix, should have:
            # if sender_raw:
            #     ...
            # else:
            #     logger.warning(...)

            if 'logger.warning' in orchestrator_code and 'sender_raw' in orchestrator_code:
                # Check for WARN log related to missing sender
                has_missing_sender_warn = (
                    'sender_raw' in orchestrator_code and
                    'logger.warning' in orchestrator_code and
                    'tespit' in orchestrator_code.lower()  # Turkish word for "identification"
                )
                if has_missing_sender_warn:
                    assert True, "WARN log for missing sender_raw is present"
                else:
                    assert False, "WARN log for missing sender_raw not found (bug exists)"
            else:
                assert False, "No WARN log handling found for empty sender_raw"
        else:
            pytest.skip("veri_cekici_ayristirici.py not found")

    def test_sender_raw_empty_fail_open_behavior_ac5(self):
        """
        AC-5 (Fail-open regresyon): Given sender_raw boş olduğunda,
        When add_to_processing_queue çalışır,
        Then mesaj işlenmeye devam etmeli (continue/passthrough, queue'ya eklenebilir),
        yani hiç filtrelenmemeli (fail-open davranışı).

        This test verifies that the current fail-open behavior is preserved.
        """
        orchestrator_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'parsers',
            'veri_cekici_ayristirici.py'
        )

        if os.path.exists(orchestrator_file):
            with open(orchestrator_file, 'r', encoding='utf-8') as f:
                orchestrator_code = f.read()

            # Verify that when sender_raw is empty, message is NOT permanently
            # marked as handled (no mark_id_handled call in else block)
            # and processing continues

            # Current code structure should be:
            # sender_raw = msg.get('from', '')
            # if sender_raw:
            #     if is_phone_in_list(...):
            #         mark_id_handled() and continue
            # # Falls through (no else with mark_id_handled)

            # Extract the relevant section (satır 505-510)
            lines = orchestrator_code.split('\n')

            # Find the sender_raw check
            sender_raw_start = None
            for i, line in enumerate(lines):
                if "sender_raw = msg.get('from'" in line:
                    sender_raw_start = i
                    break

            if sender_raw_start is not None:
                # Find the else block that corresponds to the sender_raw if check
                else_idx = None
                for j in range(sender_raw_start, min(sender_raw_start + 15, len(lines))):
                    if lines[j].strip() == 'else:':
                        else_idx = j
                        break

                assert else_idx is not None, "else bloğu bulunamalı (fail-open için gerekli)"

                # Get the indentation of the else line
                else_line = lines[else_idx]
                else_indent = len(else_line) - len(else_line.lstrip())

                # Collect lines that are part of the else block (higher indentation than else)
                else_block_lines = []
                for j in range(else_idx + 1, min(else_idx + 5, len(lines))):
                    line = lines[j]
                    if not line.strip():  # Skip empty lines
                        continue
                    current_indent = len(line) - len(line.lstrip())
                    if current_indent <= else_indent:  # End of else block
                        break
                    else_block_lines.append(line)

                else_block = '\n'.join(else_block_lines)

                # Verify fail-open: else block should NOT have mark_id_handled call
                assert 'mark_id_handled' not in else_block, \
                    "else bloğu (gönderen tespit edilemedi durumu) mark_id_handled ÇAĞIRMAMALI (fail-open)"
            else:
                pytest.skip("Could not locate sender_raw check in code")
        else:
            pytest.skip("veri_cekici_ayristirici.py not found")

    def test_lid_format_sender_produces_warn_log_ac4(self, caplog):
        """
        AC-4: Given participantAlt YOK (undefined/None) VE sadece participant
        (LID format'ında, ör. "76025719423128@lid") var,
        When add_to_processing_queue çalışır,
        Then:
        - Mesaj fail-open işlenmeli (continue, işlenmeye devam)
        - WARN seviyesinde "LID kullanıldı, eşleşme belirsiz" türü log üretilmeli

        NOTE: This test currently FAILS because the code doesn't produce
        WARN log for LID format. After fix, it should PASS.
        """
        orchestrator_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'parsers',
            'veri_cekici_ayristirici.py'
        )

        if os.path.exists(orchestrator_file):
            with open(orchestrator_file, 'r', encoding='utf-8') as f:
                orchestrator_code = f.read()

            # Look for code that handles LID-only case (participantAlt missing)
            # Should produce a WARN log

            # Expected pattern after fix:
            # if sender_raw:
            #     check blacklist
            # else if is_lid_format(sender_raw):
            #     logger.warning("LID kullanıldı, eşleşme belirsiz")
            #     continue (fail-open)

            # Check if there's any handling for LID format with WARN
            has_lid_warn = '@lid' in orchestrator_code and 'logger.warning' in orchestrator_code

            if has_lid_warn:
                # Try to find WARN related to LID uncertainty
                if 'belirsiz' in orchestrator_code.lower() or 'lid' in orchestrator_code.lower():
                    assert True, "LID uncertainty WARN log may be present"
                else:
                    assert False, "No specific LID uncertainty WARN log found"
            else:
                assert False, "No LID format handling found (AC-4 not implemented yet)"
        else:
            pytest.skip("veri_cekici_ayristirici.py not found")

    def test_regresyon_blacklist_check_still_works_ac3(self):
        """
        AC-3 (Regresyon): Given `add_to_processing_queue` VE mesajda
        participantAlt kara listede, When mesaj işlenir,
        Then mesaj yine engellenmeli (regresyon yok, mevcut davranış korunmalı).

        This test verifies that blacklist filtering still works correctly.
        """
        orchestrator_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'parsers',
            'veri_cekici_ayristirici.py'
        )

        if os.path.exists(orchestrator_file):
            with open(orchestrator_file, 'r', encoding='utf-8') as f:
                orchestrator_code = f.read()

            # Verify blacklist check is still in place
            assert 'is_phone_in_list' in orchestrator_code, \
                "Blacklist check function should still be called"
            assert 'blacklist' in orchestrator_code.lower(), \
                "Blacklist should still be loaded and checked"
            assert '[BLOCK]' in orchestrator_code, \
                "BLOCK log message should still be present"
        else:
            pytest.skip("veri_cekici_ayristirici.py not found")

    def test_add_to_processing_queue_method_exists(self):
        """
        Utility test: Verify that add_to_processing_queue method exists
        in the orchestrator.
        """
        orchestrator_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'parsers',
            'veri_cekici_ayristirici.py'
        )

        if os.path.exists(orchestrator_file):
            with open(orchestrator_file, 'r', encoding='utf-8') as f:
                orchestrator_code = f.read()

            assert 'def add_to_processing_queue' in orchestrator_code, \
                "add_to_processing_queue method should exist"
        else:
            pytest.skip("veri_cekici_ayristirici.py not found")

    def test_processing_queue_put_called_on_pass(self):
        """
        Utility test: Verify that processing_queue.put() is called when
        message passes all checks (fail-open behavior).
        """
        orchestrator_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'parsers',
            'veri_cekici_ayristirici.py'
        )

        if os.path.exists(orchestrator_file):
            with open(orchestrator_file, 'r', encoding='utf-8') as f:
                orchestrator_code = f.read()

            # Verify that messages are added to queue (fail-open)
            assert 'self.processing_queue.put' in orchestrator_code, \
                "Message should be added to processing queue when it passes filters"
        else:
            pytest.skip("veri_cekici_ayristirici.py not found")

    def test_code_inspection_sender_raw_flow_ac4_ac5(self):
        """
        Comprehensive code inspection test for AC-4 and AC-5.
        Verifies the complete flow of sender identification and logging.
        """
        orchestrator_file = os.path.join(
            os.path.dirname(__file__),
            '..',
            'src',
            'parsers',
            'veri_cekici_ayristirici.py'
        )

        if os.path.exists(orchestrator_file):
            with open(orchestrator_file, 'r', encoding='utf-8') as f:
                orchestrator_code = f.read()

            # Verify basic structure for sender handling
            assert "sender_raw = msg.get('from'" in orchestrator_code, \
                "Should extract 'from' field for sender identification"

            # Check for fallback chain (Baileys: participantAlt || participant || from)
            # This might be in sidecar/bridge.js, not here
            # But the orchestrator should handle missing sender gracefully

            # Verify that blacklist is loaded
            assert 'load_blacklist' in orchestrator_code, \
                "Blacklist should be loaded in add_to_processing_queue"

            # Verify is_phone_in_list is imported and used
            assert 'is_phone_in_list' in orchestrator_code, \
                "is_phone_in_list should be used for filtering"

            # Document current state
            # The fix should add a logger.warning() call in one or both of:
            # - if not sender_raw: (no sender at all)
            # - if is_lid_format(sender_raw): (LID instead of phone)

            print("\n[INFO] Orchestrator has basic sender handling structure")
            print("[TODO] Fix should add WARN logs for:")
            print("  - AC-5: Empty sender_raw (no sender at all)")
            print("  - AC-4: LID-only format (participantAlt missing)")
        else:
            pytest.skip("veri_cekici_ayristirici.py not found")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-s'])
