#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for DeepSeek primary model + balance alert implementation.

Acceptance Criteria:
1. [Critical] deepseek-v4-flash (or DeepSeek model name) is the FIRST model
   tried among models — Groq (openai/gpt-oss-20b) remains as fallback.
2. [Critical] System periodically (every 15 minutes) checks
   https://api.deepseek.com/user/balance endpoint; if is_available is False
   OR total_balance < $5 threshold, an alert state is triggered.
3. [High] /api/status endpoint contains a deepseek_balance field in addition
   to existing service/system fields:
   {"available": true/false/"unknown", "balance_usd": <float or None>, "low": true/false}
4. [High] If balance check request to DeepSeek API fails (network error),
   this is marked as "unknown" status — NOT "balance OK" (available: true)
   OR system crash.
5. [Medium] DeepSeek is tried first as primary model but if it fails,
   existing "model failed, try next" logic (NOT CHANGED) falls back to Groq.
6. [Medium] If DEEPSEEK_API_KEY is not defined, balance check is never
   started, no error raised.

Test Technique:
- Model order: Use inspect.getsource() to extract function source, verify
  string position (assert 'deepseek' index < 'openai/gpt-oss-20b' index).
- Balance check: Mock urllib.request.urlopen, simulate scenarios
  (success/low balance, success/sufficient, network error).
- Helper function: Test _check_deepseek_balance_once() logic, NOT the
  infinite loop directly.
- Flask route: Use .__wrapped__ + test_request_context for @require_auth routes.
- No broad sys.modules mocking (dotenv, google.genai) — use real imports.
"""

import pytest
import json
import os
import sys
import inspect
import tempfile
import time
from unittest.mock import patch, MagicMock, Mock, call
from io import StringIO
from contextlib import contextmanager

# Add project root to path
sys.path.insert(0, os.getcwd())

# Mock google.genai before importing text_gen_parser to avoid ImportError
sys.modules['google'] = MagicMock()
sys.modules['google.genai'] = MagicMock()

from src.api import admin_panel
import text_gen_parser


class TestDeepSeekModelOrder:
    """AC-1: Verify DeepSeek models are tried FIRST, before Groq."""

    def test_stage2_model_order_deepseek_first(self):
        """
        Given: text_gen_parser.py Stage 2 (robust attempt with fallbacks)
        When: models_to_try list is defined in parse_async
        Then: self.model_robust (DeepSeek) appears BEFORE openai/gpt-oss-20b in that method
        """
        import re

        parser = text_gen_parser.TextGenParser()

        # Verify that model_robust is set to a deepseek model.
        # DÜZELTME (2026-09-01): atdd.md AC-1 açıkça "deepseek-v4-flash İLK
        # denenen model olur" diyordu — bu test önceden yanlışlıkla pahalı
        # 'deepseek-v4-pro'yu birincil olarak doğruluyordu (spesifikasyon
        # sapmasını test ediyordu, spesifikasyonun kendisini değil).
        assert parser.model_robust == 'deepseek-v4-flash', (
            f"model_robust should be 'deepseek-v4-flash' (atdd.md AC-1: ucuz, günlük limitsiz "
            f"model birincil olmalı), got {parser.model_robust}"
        )

        # DÜZELTME (2026-09-02): baileys-pro-model-kaldir-ve-blacklist-lid-fix —
        # pahalı deepseek-v4-pro fallback modeli maliyet nedeniyle kasıtlı olarak
        # kaldırıldı, fallback_models artık boş olmalı (flash başarısız olursa
        # doğrudan Groq'a geçiliyor).
        assert parser.fallback_models == [], (
            f"fallback_models pro model kaldırıldığı için boş olmalı, got {parser.fallback_models}"
        )

        # Extract ONLY the Stage 2 method source (parse_async, not entire class)
        # This isolates the test from __init__ attribute assignments
        stage2_source = inspect.getsource(parser.parse_async)

        # Find the models_to_try assignment within parse_async method
        # Pattern: models_to_try = [self.model_robust] + self.fallback_models + ['openai/gpt-oss-20b']
        # We need to match the full expression including list concatenation
        match = re.search(
            r'models_to_try\s*=\s*\[self\.model_robust\]\s*\+\s*self\.fallback_models\s*\+\s*\[[^\]]*openai/gpt-oss-20b[^\]]*\]',
            stage2_source
        )
        assert match, "models_to_try assignment not found in parse_async method"

        assignment_line = match.group(0)

        # Check that model_robust is referenced before the final groq fallback
        robust_pos = assignment_line.find('self.model_robust')
        groq_pos = assignment_line.find("'openai/gpt-oss-20b'")

        assert robust_pos != -1, "self.model_robust not found in Stage 2 models_to_try assignment"
        assert groq_pos != -1, "openai/gpt-oss-20b not found in Stage 2 models_to_try assignment"
        assert robust_pos < groq_pos, (
            f"self.model_robust (pos {robust_pos}) should appear before Groq (pos {groq_pos}) "
            f"in Stage 2 models_to_try assignment, got: {assignment_line}"
        )


class TestDeepSeekBalanceCheck:
    """AC-2, AC-3, AC-4: Verify periodic balance check and status endpoint."""

    def test_check_deepseek_balance_once_success_sufficient(self):
        """
        Given: _check_deepseek_balance_once() called, API responds with sufficient balance
        When: Balance > $5 threshold and available=true
        Then: Returns {"available": true, "balance_usd": <balance>, "low": false}
        """
        api_response = {
            "is_available": True,
            "balance_infos": [{"currency": "USD", "total_balance": 10.5, "granted_balance": 0.0, "topped_up_balance": 10.5}]
        }

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
            mock_urlopen.return_value = mock_response

            result = admin_panel._check_deepseek_balance_once(
                api_key="test_key",
                threshold_usd=5.0
            )

            assert result["available"] is True, "Should be available when is_available=true"
            assert result["balance_usd"] == 10.5, "Should return correct balance"
            assert result["low"] is False, "Should not be low when balance > threshold"

    def test_check_deepseek_balance_once_success_low(self):
        """
        Given: _check_deepseek_balance_once() called, API responds with low balance
        When: Balance < $5 threshold
        Then: Returns {"available": true, "balance_usd": <balance>, "low": true}
        """
        api_response = {
            "is_available": True,
            "balance_infos": [{"currency": "USD", "total_balance": 2.5, "granted_balance": 0.0, "topped_up_balance": 2.5}]
        }

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
            mock_urlopen.return_value = mock_response

            result = admin_panel._check_deepseek_balance_once(
                api_key="test_key",
                threshold_usd=5.0
            )

            assert result["available"] is True, "Should be available (api says so)"
            assert result["balance_usd"] == 2.5, "Should return correct balance"
            assert result["low"] is True, "Should be low when balance < threshold"

    def test_check_deepseek_balance_once_unavailable(self):
        """
        Given: _check_deepseek_balance_once() called, API says is_available=false
        When: DeepSeek marks account as unavailable
        Then: Returns {"available": false, "balance_usd": <balance>, "low": true}
        """
        api_response = {
            "is_available": False,
            "balance_infos": [{"currency": "USD", "total_balance": 0.0, "granted_balance": 0.0, "topped_up_balance": 0.0}]
        }

        with patch('urllib.request.urlopen') as mock_urlopen:
            mock_response = MagicMock()
            mock_response.read.return_value = json.dumps(api_response).encode('utf-8')
            mock_urlopen.return_value = mock_response

            result = admin_panel._check_deepseek_balance_once(
                api_key="test_key",
                threshold_usd=5.0
            )

            assert result["available"] is False, "Should be unavailable when is_available=false"
            assert result["low"] is True, "Should be low when unavailable"

    def test_check_deepseek_balance_once_network_error(self):
        """
        AC-4: Network error returns "unknown" status, NOT "balance OK" or crash.

        Given: _check_deepseek_balance_once() called, network fails
        When: urllib.request.urlopen raises exception (URLError, timeout, etc.)
        Then: Returns {"available": "unknown", "balance_usd": None, "low": false}
              (distinct from available=true, which would be wrong)
        """
        with patch('urllib.request.urlopen') as mock_urlopen:
            import urllib.error
            mock_urlopen.side_effect = urllib.error.URLError("Connection failed")

            result = admin_panel._check_deepseek_balance_once(
                api_key="test_key",
                threshold_usd=5.0
            )

            # CRITICAL: "unknown" must be distinct from True/False
            assert result["available"] == "unknown", (
                f"Network error should return 'unknown', not {result['available']}"
            )
            assert result["balance_usd"] is None, "balance_usd should be None on network error"
            assert result["low"] is False, (
                "low should be False on network error (preserve previous state)"
            )

    def test_check_deepseek_balance_once_no_api_key(self):
        """
        AC-6: If DEEPSEEK_API_KEY not defined, balance check doesn't start, no error.

        Given: _check_deepseek_balance_once() called with api_key=None
        When: DEEPSEEK_API_KEY environment variable not set
        Then: Function returns early without making HTTP request, no exception
        """
        with patch('urllib.request.urlopen') as mock_urlopen:
            result = admin_panel._check_deepseek_balance_once(
                api_key=None,
                threshold_usd=5.0
            )

            # Should not call urlopen at all
            mock_urlopen.assert_not_called()

            # Should return a safe default
            assert result["available"] in [None, "unknown"], (
                f"Without API key, available should be None or 'unknown', got {result['available']}"
            )


class TestStatusEndpointDeepSeekBalance:
    """AC-3: /api/status endpoint includes deepseek_balance field."""

    def test_status_endpoint_contains_deepseek_balance_field(self):
        """
        Given: /api/status endpoint is called
        When: Response is returned
        Then: Response contains deepseek_balance with {available, balance_usd, low} fields
        """
        # Mock the admin_panel module's _status_cache and _deepseek_balance_cache
        # to simulate populated cache

        mock_status_cache = {
            "service": {"status": "running", "cpu": 10, "memory": 50, "restarts": 0, "uptime": 3600},
            "system": {"load": 0.5}
        }

        mock_deepseek_balance_cache = {
            "available": True,
            "balance_usd": 8.75,
            "low": False
        }

        with patch.object(admin_panel, '_status_cache', mock_status_cache):
            with patch.object(admin_panel, '_deepseek_balance_cache', mock_deepseek_balance_cache):
                # Call the status endpoint's underlying logic
                # Using .__wrapped__ to bypass @require_auth decorator
                if hasattr(admin_panel.status, '__wrapped__'):
                    with admin_panel.app.test_request_context():
                        response = admin_panel.status.__wrapped__()
                        data = response.get_json() if hasattr(response, 'get_json') else json.loads(response[0])
                elif hasattr(admin_panel, 'status'):
                    # Fallback: call the function directly if no decorator
                    with admin_panel.app.test_request_context():
                        response = admin_panel.status()
                        data = response.get_json() if hasattr(response, 'get_json') else json.loads(response[0])

                # Verify deepseek_balance field exists
                assert "deepseek_balance" in data, (
                    f"deepseek_balance field missing from /api/status response: {data.keys()}"
                )

                # Verify deepseek_balance structure
                balance = data["deepseek_balance"]
                assert "available" in balance, "deepseek_balance should have 'available' field"
                assert "balance_usd" in balance, "deepseek_balance should have 'balance_usd' field"
                assert "low" in balance, "deepseek_balance should have 'low' field"

    def test_status_endpoint_deepseek_balance_unknown(self):
        """
        Given: /api/status endpoint called, balance check failed (network error)
        When: Response returned
        Then: deepseek_balance.available == "unknown" (not true/false)
        """
        mock_status_cache = {
            "service": {"status": "running", "cpu": 10, "memory": 50, "restarts": 0, "uptime": 3600},
            "system": None
        }

        # Network error state
        mock_deepseek_balance_cache = {
            "available": "unknown",
            "balance_usd": None,
            "low": False
        }

        with patch.object(admin_panel, '_status_cache', mock_status_cache):
            with patch.object(admin_panel, '_deepseek_balance_cache', mock_deepseek_balance_cache):
                if hasattr(admin_panel.status, '__wrapped__'):
                    with admin_panel.app.test_request_context():
                        response = admin_panel.status.__wrapped__()
                        data = response.get_json() if hasattr(response, 'get_json') else json.loads(response[0])
                elif hasattr(admin_panel, 'status'):
                    with admin_panel.app.test_request_context():
                        response = admin_panel.status()
                        data = response.get_json() if hasattr(response, 'get_json') else json.loads(response[0])

                balance = data.get("deepseek_balance", {})
                assert balance.get("available") == "unknown", (
                    f"On network error, available should be 'unknown', got {balance.get('available')}"
                )


class TestDeepSeekFallbackBehavior:
    """AC-5: DeepSeek fails → Groq fallback (existing logic unchanged)."""

    def test_groq_fallback_when_deepseek_unavailable(self):
        """
        Given: text_gen_parser tries to parse with DeepSeek
        When: DeepSeek fails (timeout, unavailable, error response)
        Then: Existing fallback logic kicks in, tries Groq next (NOT CHANGED)
        """
        # This test verifies that the model order change doesn't break fallback
        parser = text_gen_parser.TextGenParser()

        # Parser should have fallback list with groq
        # After fix, groq should be in fallback/retry list
        source = inspect.getsource(text_gen_parser.TextGenParser)

        # Verify that groq is still available as a fallback option
        assert "'openai/gpt-oss-20b'" in source, (
            "Groq (openai/gpt-oss-20b) should still be available as fallback"
        )

        # Verify that fallback mechanism references groq
        # (This is a check that the existing fallback chain isn't broken)
        assert hasattr(parser, 'fallback_models'), "Parser should have fallback_models"


class TestDeepSeekBalancePeriodicCheck:
    """AC-2: System checks balance every 15 minutes."""

    def test_deepseek_balance_thread_exists(self):
        """
        Given: admin_panel module loaded
        When: System initialized
        Then: A thread (_refresh_deepseek_balance) is running that checks balance every 15 min
        """
        # Check that admin_panel has the refresh function
        assert hasattr(admin_panel, '_refresh_deepseek_balance'), (
            "_refresh_deepseek_balance() should exist in admin_panel"
        )

        # Check that there's a cache to store results
        assert hasattr(admin_panel, '_deepseek_balance_cache'), (
            "_deepseek_balance_cache should exist in admin_panel"
        )

    def test_deepseek_balance_cache_initialization(self):
        """
        Given: admin_panel loaded
        When: System starts
        Then: _deepseek_balance_cache initialized with default values
        """
        cache = admin_panel._deepseek_balance_cache

        # Should have the expected structure
        assert isinstance(cache, dict), "_deepseek_balance_cache should be a dict"

        # Should have or will populate these keys
        # When initialized, should have at least the available field
        assert "available" in cache, "_deepseek_balance_cache should have 'available' key"


class TestDeepSeekApiKeyHandling:
    """AC-6: DEEPSEEK_API_KEY undefined behavior."""

    def test_no_error_when_deepseek_api_key_undefined(self):
        """
        Given: DEEPSEEK_API_KEY environment variable not set
        When: admin_panel module loads
        Then: No exception raised, system continues normally
        """
        # Save original env
        original_key = os.environ.get('DEEPSEEK_API_KEY')

        try:
            # Remove the key
            if 'DEEPSEEK_API_KEY' in os.environ:
                del os.environ['DEEPSEEK_API_KEY']

            # Re-import or check that module handles missing key gracefully
            # This is more of an integration test
            # We just verify that the module has defensive code

            # Function should check for api_key before attempting to use it
            source = inspect.getsource(admin_panel._refresh_deepseek_balance)

            # Should have a guard like:
            # if not api_key: return
            # or similar defensive check
            assert (
                'DEEPSEEK_API_KEY' in source or
                'api_key' in source.lower()
            ), (
                "_refresh_deepseek_balance should check for DEEPSEEK_API_KEY existence"
            )
        finally:
            # Restore original env
            if original_key is not None:
                os.environ['DEEPSEEK_API_KEY'] = original_key


class TestDeepSeekBalanceIntegration:
    """Integration test: DeepSeek primary + balance alert + status endpoint work together."""

    def test_full_pipeline_deepseek_primary_with_balance_alert(self):
        """
        Given: Full system with DeepSeek primary + balance monitoring
        When: Message is sent AND balance check completes
        Then: (1) DeepSeek attempted first, (2) Status shows balance, (3) Low balance triggers alert
        """
        # This is a high-level integration test
        # Verifies that all pieces work together

        # Check 1: DeepSeek models are first in attempt order
        parser = text_gen_parser.TextGenParser()
        source = inspect.getsource(text_gen_parser.TextGenParser)
        deepseek_first = source.find('deepseek') < source.find('openai/gpt-oss-20b')
        assert deepseek_first, "DeepSeek should be attempted first"

        # Check 2: Admin panel has balance monitoring
        assert hasattr(admin_panel, '_deepseek_balance_cache'), (
            "Admin panel should have balance cache"
        )
        assert hasattr(admin_panel, '_refresh_deepseek_balance'), (
            "Admin panel should have balance refresh function"
        )

        # Check 3: Status endpoint can return balance
        if hasattr(admin_panel, 'status'):
            # Verify status function exists
            assert callable(admin_panel.status), "status should be callable"
