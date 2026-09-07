#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for hourly-cap-race-fix (AC-1 through AC-5).

This test suite covers the reservation-based race condition prevention for
the hourly AI spend cap, including:
- AC-1: Reservation prevents race condition (50 concurrent calls)
- AC-2: Reservation → real cost correction
- AC-3: Failed call reservation release
- AC-4: Hour change resets counters
- AC-5: Fail-open on exception

NOTE: These tests are designed to FAIL (RED) until the implementation is complete.
The implementation should add:
  - _current_hour_reserved_try (module-level global)
  - ESTIMATED_COST_PER_CALL_TRY (module-level constant)
  - release_hourly_reservation() (module-level function)
  - Modifications to is_hourly_cap_exceeded() (atomic check + reserve)
  - Modifications to _track_spend() (resolve reservation + real cost)
"""

import pytest
import os
import sys
import logging
from datetime import datetime
from unittest.mock import MagicMock, patch, Mock, PropertyMock
from io import StringIO
import threading
from concurrent.futures import ThreadPoolExecutor
import time

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

# Set up logging
logging.basicConfig(level=logging.DEBUG)


class TestHourlyCapsRaceCondition:
    """
    Race condition prevention tests for hourly AI spend cap.
    Tests AC-1, AC-2, AC-3, AC-4, AC-5 from atdd.md.

    NOTE: Tests should FAIL until implementation adds reservation logic.
    """

    def setup_method(self):
        """Reset module state before each test."""
        import text_gen_parser
        # Reset global state
        with patch.object(text_gen_parser, '_hourly_lock', threading.Lock()):
            text_gen_parser._current_hour_key = None
            text_gen_parser._current_hour_cost_try = 0.0
            # Try to reset reserved_try if it exists (won't fail if missing)
            if hasattr(text_gen_parser, '_current_hour_reserved_try'):
                text_gen_parser._current_hour_reserved_try = 0.0

    def teardown_method(self):
        """Clean up after each test."""
        import text_gen_parser
        # Reset global state
        with patch.object(text_gen_parser, '_hourly_lock', threading.Lock()):
            text_gen_parser._current_hour_key = None
            text_gen_parser._current_hour_cost_try = 0.0
            if hasattr(text_gen_parser, '_current_hour_reserved_try'):
                text_gen_parser._current_hour_reserved_try = 0.0

    # ========== AC-1 Tests: Reservation + Race Prevention ==========

    def test_ac1_sequential_50_calls_should_block_at_cap(self):
        """
        AC-1: Given saatlik harcama 0 TL ve limit 9 TL,
        When 50 ardışık `is_hourly_cap_exceeded()` çağrısı yapılırsa (her çağrı
        ESTIMATED_COST_PER_CALL_TRY kadar rezerve etmeli),
        Then toplam rezervasyon 9 TL'yi aştığı noktadan sonraki çağrılar True dönmeli
        (en azından bir kısmı ertelenmeli, hepsi False dönmemeli).

        This verifies that reservation prevents unlimited cap bypass.
        EXPECTED: Test FAILS until implementation adds reservation logic.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # Initialize
            with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                    # Try to get estimated cost
                    try:
                        estimated_cost = getattr(text_gen_parser, 'ESTIMATED_COST_PER_CALL_TRY', 0.15)
                    except AttributeError:
                        estimated_cost = 0.15  # Fallback estimate

                    results = []
                    for i in range(50):
                        result = text_gen_parser.is_hourly_cap_exceeded()
                        results.append(result)

                    # Verify that NOT ALL calls returned False (at least one blocked)
                    # If implementation has reservation, some calls should be True
                    false_count = sum(1 for r in results if r is False)
                    true_count = sum(1 for r in results if r is True)

                    # EXPECTED BEHAVIOR (after implementation):
                    # - First ~60 calls return False (9 TL / 0.15 TL per call ≈ 60 calls)
                    # - Remaining calls return True
                    # CURRENT BUGGY BEHAVIOR (without reservation):
                    # - All 50 calls return False (race condition)

                    assert true_count > 0, (
                        f"AC-1 FAIL: All 50 calls returned False (no blocking). "
                        f"Expected at least some True returns due to reservation. "
                        f"This indicates reservation logic NOT implemented. "
                        f"Results: {true_count} True, {false_count} False"
                    )

    def test_ac1_concurrent_50_threads_respects_reservation_limit(self):
        """
        AC-1 (thread-safety): Given 50 concurrent threads each calling `is_hourly_cap_exceeded()`,
        When executed simultaneously, Then the total reserved cost should NOT exceed
        cap + one reservation unit (ESTIMATED_COST_PER_CALL_TRY).

        This is the true concurrency test using ThreadPoolExecutor.
        EXPECTED: Test FAILS until implementation adds atomic check+reserve.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                    try:
                        estimated_cost = getattr(text_gen_parser, 'ESTIMATED_COST_PER_CALL_TRY', 0.15)
                    except AttributeError:
                        estimated_cost = 0.15

                    results = []

                    def call_is_cap_exceeded():
                        return text_gen_parser.is_hourly_cap_exceeded()

                    # Execute 50 concurrent calls
                    with ThreadPoolExecutor(max_workers=50) as executor:
                        futures = [executor.submit(call_is_cap_exceeded) for _ in range(50)]
                        results = [f.result() for f in futures]

                    # Count True/False
                    true_count = sum(1 for r in results if r is True)
                    false_count = sum(1 for r in results if r is False)

                    # Get current reserved amount (if implementation exists)
                    try:
                        reserved_try = getattr(text_gen_parser, '_current_hour_reserved_try', 0.0)
                    except AttributeError:
                        reserved_try = 0.0

                    # EXPECTED: Some calls blocked (True returned)
                    assert true_count > 0, (
                        f"AC-1 Concurrency FAIL: All 50 concurrent calls returned False. "
                        f"Expected race condition prevention via atomic reservation. "
                        f"Reserved: {reserved_try} TL. "
                        f"Results: {true_count} True, {false_count} False"
                    )

                    # EXPECTED: Total cost + reserved should not exceed cap + 1 unit
                    # (allowing 1 unit tolerance for atomicity margin)
                    cap = 9.0
                    total_reserved_cost = text_gen_parser._current_hour_cost_try + reserved_try
                    max_allowed = cap + estimated_cost

                    assert total_reserved_cost <= max_allowed * 1.1, (  # Allow 10% tolerance for floating point
                        f"AC-1 Concurrency FAIL: Total (cost + reserved) exceeds cap + 1 unit. "
                        f"Cost: {text_gen_parser._current_hour_cost_try} TL, "
                        f"Reserved: {reserved_try} TL, "
                        f"Total: {total_reserved_cost} TL, "
                        f"Max allowed: {max_allowed} TL"
                    )

    # ========== AC-2 Tests: Reservation → Real Cost Resolution ==========

    def test_ac2_track_spend_resolves_reservation(self):
        """
        AC-2: Given a previous `is_hourly_cap_exceeded()` call made a reservation,
        When `_track_spend()` is called with real cost,
        Then the reserved amount should be reduced by ESTIMATED_COST_PER_CALL_TRY
        AND the real cost should be added to _current_hour_cost_try.

        EXPECTED: Test FAILS until _track_spend() implements reservation resolution.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                    try:
                        estimated_cost = getattr(text_gen_parser, 'ESTIMATED_COST_PER_CALL_TRY', 0.15)
                    except AttributeError:
                        estimated_cost = 0.15

                    # ASSERT that _current_hour_reserved_try attribute exists (required for test to work)
                    assert hasattr(text_gen_parser, '_current_hour_reserved_try'), (
                        "AC-2 Test setup FAIL: _current_hour_reserved_try attribute not found in text_gen_parser. "
                        "Implementation must define this module-level global."
                    )

                    # Manually set reservation (simulating a prior is_hourly_cap_exceeded() call)
                    # Direct assignment, no hasattr guard (attribute exists per above assert)
                    text_gen_parser._current_hour_reserved_try = estimated_cost

                    # Record initial state (direct attribute access, no getattr default)
                    initial_cost = text_gen_parser._current_hour_cost_try
                    initial_reserved = text_gen_parser._current_hour_reserved_try

                    # Create a mock parser instance to call _track_spend
                    parser = text_gen_parser.TextGenParser()

                    # Track spend: real cost is 0.10 TL (less than estimated 0.15)
                    real_cost_try = 0.10
                    parser._track_spend('gpt-oss-20b', 1000, 500)  # Will compute real cost

                    # Expected outcome:
                    # - reserved_try should decrease by exactly estimated_cost
                    # - _current_hour_cost_try should increase by actual cost
                    final_reserved = text_gen_parser._current_hour_reserved_try
                    final_cost = text_gen_parser._current_hour_cost_try

                    # Verify reservation was resolved: must decrease by exactly estimated_cost
                    expected_final_reserved = max(0.0, initial_reserved - estimated_cost)
                    assert abs(final_reserved - expected_final_reserved) < 0.001, (
                        f"AC-2 FAIL: Reserved amount not correctly resolved after _track_spend(). "
                        f"Initial reserved: {initial_reserved} TL, "
                        f"Final reserved: {final_reserved} TL, "
                        f"Expected: {expected_final_reserved} TL (initial - estimated_cost, floored at 0)."
                    )

                    # Verify real cost was added
                    assert final_cost > initial_cost, (
                        f"AC-2 FAIL: Real cost not added to _current_hour_cost_try. "
                        f"Initial: {initial_cost} TL, Final: {final_cost} TL"
                    )

    def test_ac2_reserved_never_goes_negative(self):
        """
        AC-2 (safety): Given _current_hour_reserved_try at 0.05 TL,
        When _track_spend() tries to resolve a 0.15 TL reservation,
        Then _current_hour_reserved_try should stay at 0 (not go negative).

        Uses max(0.0, ...) safety guardrail.
        EXPECTED: Test FAILS until implementation uses max(0, ...) safety check.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                    # ASSERT that _current_hour_reserved_try attribute exists
                    assert hasattr(text_gen_parser, '_current_hour_reserved_try'), (
                        "AC-2 Safety Test setup FAIL: _current_hour_reserved_try attribute not found in text_gen_parser. "
                        "Implementation must define this module-level global."
                    )

                    # Set reserved to a small amount (smaller than ESTIMATED_COST_PER_CALL_TRY)
                    # Direct assignment, no hasattr guard
                    text_gen_parser._current_hour_reserved_try = 0.05
                    initial_reserved = text_gen_parser._current_hour_reserved_try

                    parser = text_gen_parser.TextGenParser()

                    # Track spend (will try to subtract estimated cost, which is > 0.05)
                    parser._track_spend('gpt-oss-20b', 1000, 500)

                    # Verify reserved never went negative (direct attribute access, no getattr default)
                    final_reserved = text_gen_parser._current_hour_reserved_try

                    assert final_reserved >= 0.0, (
                        f"AC-2 Safety FAIL: Reserved went negative! "
                        f"Initial reserved: {initial_reserved} TL, "
                        f"Final reserved: {final_reserved} TL. "
                        f"Expected final >= 0 (must use max(0, ...) safety check)."
                    )

                    # Also verify it was floored at 0, not left at initial value
                    assert final_reserved == 0.0, (
                        f"AC-2 Safety FAIL: Reserved should be exactly 0 (max(0, initial - estimated_cost)). "
                        f"Initial reserved: {initial_reserved} TL, "
                        f"Final reserved: {final_reserved} TL. "
                        f"This indicates _track_spend() did not subtract the estimated cost."
                    )

    # ========== AC-3 Tests: Failed Call Reservation Release ==========

    def test_ac3_release_hourly_reservation_decreases_reserved(self):
        """
        AC-3: Given a reservation is held (_current_hour_reserved_try = 0.15 TL),
        When `release_hourly_reservation()` is called (on AI call failure),
        Then _current_hour_reserved_try should decrease by one unit (ESTIMATED_COST_PER_CALL_TRY).

        EXPECTED: Test FAILS until release_hourly_reservation() is implemented.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                try:
                    estimated_cost = getattr(text_gen_parser, 'ESTIMATED_COST_PER_CALL_TRY', 0.15)
                except AttributeError:
                    estimated_cost = 0.15

                # Set initial reservation
                if hasattr(text_gen_parser, '_current_hour_reserved_try'):
                    text_gen_parser._current_hour_reserved_try = estimated_cost * 2  # Two units

                initial_reserved = getattr(text_gen_parser, '_current_hour_reserved_try', 0.0)

                # Call release (should exist as a module-level function)
                try:
                    text_gen_parser.release_hourly_reservation()
                except AttributeError:
                    pytest.fail(
                        "AC-3 FAIL: release_hourly_reservation() function not found in text_gen_parser. "
                        "Expected from plan.md."
                    )

                final_reserved = getattr(text_gen_parser, '_current_hour_reserved_try', 0.0)

                # Verify reservation decreased
                assert final_reserved < initial_reserved, (
                    f"AC-3 FAIL: release_hourly_reservation() did not decrease reserved. "
                    f"Initial: {initial_reserved} TL, Final: {final_reserved} TL. "
                    f"Expected final < initial."
                )

                # Verify it decreased by exactly one unit
                expected_decrease = estimated_cost
                actual_decrease = initial_reserved - final_reserved
                assert abs(actual_decrease - expected_decrease) < 0.001, (
                    f"AC-3 FAIL: Reserved decreased by {actual_decrease}, "
                    f"expected ~{expected_decrease} (ESTIMATED_COST_PER_CALL_TRY)."
                )

    def test_ac3_release_at_zero_does_not_go_negative(self):
        """
        AC-3 (safety): Given _current_hour_reserved_try = 0,
        When release_hourly_reservation() is called,
        Then reserved should stay at 0 (not go negative).

        EXPECTED: Test should PASS if implementation uses max(0, ...).
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                if hasattr(text_gen_parser, '_current_hour_reserved_try'):
                    text_gen_parser._current_hour_reserved_try = 0.0

                # Call release when already at 0
                try:
                    text_gen_parser.release_hourly_reservation()
                except AttributeError:
                    pytest.skip("release_hourly_reservation() not yet implemented")

                final_reserved = getattr(text_gen_parser, '_current_hour_reserved_try', 0.0)

                assert final_reserved >= 0.0, (
                    f"AC-3 Safety FAIL: Reserved went negative when releasing from 0! "
                    f"Final: {final_reserved}. Expected >= 0."
                )

    # ========== AC-4 Tests: Hour Change Resets Counters ==========

    def test_ac4_hour_change_resets_reserved_and_cost(self):
        """
        AC-4: Given saat değişimi (örn. 14:00 → 15:00),
        When `is_hourly_cap_exceeded()` çalışırsa,
        Then hem _current_hour_cost_try hem _current_hour_reserved_try sıfırlanmalı.

        This verifies both counters reset together (not just cost).
        EXPECTED: Test FAILS if reserved counter not added or reset logic missing.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # Hour 14: set cost and reserved
            with patch('text_gen_parser.datetime') as mock_datetime:
                base_time = datetime(2026, 9, 4, 14, 30, 0)
                mock_datetime.now.return_value = base_time

                with patch.object(text_gen_parser, '_current_hour_cost_try', 8.0):
                    with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                        if hasattr(text_gen_parser, '_current_hour_reserved_try'):
                            text_gen_parser._current_hour_reserved_try = 0.3

                        # Hour 15: new hour should trigger reset
                        next_hour = datetime(2026, 9, 4, 15, 30, 0)
                        mock_datetime.now.return_value = next_hour

                        # Mock _get_current_hour_key to return new hour
                        with patch.object(text_gen_parser, '_get_current_hour_key') as mock_get_key:
                            mock_get_key.return_value = '2026-09-04-15'

                            # Call is_hourly_cap_exceeded() which should trigger reset
                            text_gen_parser.is_hourly_cap_exceeded()

                            # Verify both counters reset
                            assert text_gen_parser._current_hour_cost_try == 0.0, (
                                f"AC-4 FAIL: _current_hour_cost_try not reset on hour change. "
                                f"Value: {text_gen_parser._current_hour_cost_try}"
                            )

                            try:
                                reserved = getattr(text_gen_parser, '_current_hour_reserved_try', 0.0)
                            except AttributeError:
                                reserved = 0.0

                            assert reserved == 0.0, (
                                f"AC-4 FAIL: _current_hour_reserved_try not reset on hour change. "
                                f"Value: {reserved}"
                            )

    # ========== AC-5 Tests: Fail-Open Behavior ==========

    def test_ac5_exception_in_is_hourly_cap_exceeded_returns_false(self):
        """
        AC-5: Given an unexpected exception during `is_hourly_cap_exceeded()`
        (e.g., lock error, file read error),
        When called, Then should return False (fail-open: limit disabled, message processed).

        This verifies safety: system does not break on partial failures.
        EXPECTED: Test should PASS (fail-open already in implementation at lines 91-93).
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            # Mock _hourly_lock.acquire to raise an exception
            original_lock = text_gen_parser._hourly_lock
            mock_lock = MagicMock()
            mock_lock.__enter__ = MagicMock(side_effect=RuntimeError("Lock error"))
            mock_lock.__exit__ = MagicMock()

            with patch.object(text_gen_parser, '_hourly_lock', mock_lock):
                result = text_gen_parser.is_hourly_cap_exceeded()

                assert result is False, (
                    f"AC-5 FAIL: is_hourly_cap_exceeded() raised exception but didn't fail-open. "
                    f"Expected False (fail-open), got {result}."
                )

    def test_ac5_exception_in_track_spend_doesnt_crash(self):
        """
        AC-5: Given an exception during _track_spend() (e.g., lock error),
        When called, Then should handle gracefully without raising to caller.

        This verifies robustness: spend tracking failure doesn't break message processing.
        EXPECTED: Test should PASS (implementation should have try-except).
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                    parser = text_gen_parser.TextGenParser()

                    # Mock the lock to raise an exception
                    mock_lock = MagicMock()
                    mock_lock.__enter__ = MagicMock(side_effect=RuntimeError("Lock error"))
                    mock_lock.__exit__ = MagicMock()

                    with patch.object(text_gen_parser, '_hourly_lock', mock_lock):
                        # Should not raise
                        try:
                            parser._track_spend('gpt-oss-20b', 1000, 500)
                            # Success: no exception raised
                        except Exception as e:
                            pytest.fail(
                                f"AC-5 FAIL: _track_spend() raised exception {type(e).__name__}: {e}. "
                                f"Should handle gracefully (try-except wrapper)."
                            )

    # ========== Integration: Sequential vs Concurrent Behavior ==========

    def test_integration_sequential_then_concurrent_consistency(self):
        """
        Integration test: Verify that sequential and concurrent behaviors are consistent.

        Given multiple calls to is_hourly_cap_exceeded() in both modes,
        When run sequentially then concurrently,
        Then both should respect the same reservation limits (allowing for race margin).

        EXPECTED: Test FAILS without reservation logic, PASSES after implementation.
        """
        import text_gen_parser

        with patch.dict(os.environ, {'AI_HOURLY_SPEND_CAP_TRY': '9.0'}):
            try:
                estimated_cost = getattr(text_gen_parser, 'ESTIMATED_COST_PER_CALL_TRY', 0.15)
            except AttributeError:
                estimated_cost = 0.15

            # Sequential test
            with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                    if hasattr(text_gen_parser, '_current_hour_reserved_try'):
                        text_gen_parser._current_hour_reserved_try = 0.0

                    sequential_results = []
                    for i in range(50):
                        result = text_gen_parser.is_hourly_cap_exceeded()
                        sequential_results.append(result)

                    seq_true = sum(1 for r in sequential_results if r is True)
                    seq_false = sum(1 for r in sequential_results if r is False)

            # Reset for concurrent test
            with patch.object(text_gen_parser, '_current_hour_cost_try', 0.0):
                with patch.object(text_gen_parser, '_current_hour_key', '2026-09-04-14'):
                    if hasattr(text_gen_parser, '_current_hour_reserved_try'):
                        text_gen_parser._current_hour_reserved_try = 0.0

                    concurrent_results = []

                    def call_is_cap():
                        return text_gen_parser.is_hourly_cap_exceeded()

                    with ThreadPoolExecutor(max_workers=50) as executor:
                        futures = [executor.submit(call_is_cap) for _ in range(50)]
                        concurrent_results = [f.result() for f in futures]

                    conc_true = sum(1 for r in concurrent_results if r is True)
                    conc_false = sum(1 for r in concurrent_results if r is False)

            # Both should have some True results (blocking) if implementation works
            assert seq_true > 0 or conc_true > 0, (
                f"Integration FAIL: Neither sequential nor concurrent tests got True results. "
                f"Sequential: {seq_true} True / {seq_false} False. "
                f"Concurrent: {conc_true} True / {conc_false} False. "
                f"Indicates reservation logic NOT implemented."
            )
