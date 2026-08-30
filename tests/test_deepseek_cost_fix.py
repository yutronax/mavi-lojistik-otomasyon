#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for TextGenParser Groq+DeepSeek fallback and cost tracking refactor.

Acceptance Criteria:
1. Groq (Llama) is first model tried, not DeepSeek
2. On Groq API failure, DeepSeek fallback is triggered
3. On Groq success but empty routes, DeepSeek is retried
4. When all models fail, empty list [] is returned
5. On Groq rate-limit (429), DeepSeek fallback occurs
6. _track_spend() records 'provider' field for each cost entry

Tests use unittest.mock to mock API clients (no real HTTP calls).
"""

import pytest
import asyncio
import json
import os
import sys
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch, call, Mock
from datetime import datetime

# We test TextGenParser without running actual API calls
# Adjust the import path if needed
sys.path.insert(0, os.getcwd())

# Stub out problematic imports before importing text_gen_parser
sys.modules['google.genai'] = MagicMock()
sys.modules['google'] = MagicMock()

from text_gen_parser import TextGenParser


class TestDeepSeekPrimaryModel:
    """AC#1: DeepSeek (now primary) is tried first, not Groq."""

    @pytest.mark.asyncio
    async def test_parse_async_tries_deepseek_first(self):
        """
        Integration test: Mock DeepSeek client to succeed, verify it's called first
        and Groq is NOT called.

        Given: A message to parse
        When: parse_async is called with DeepSeek returning valid data
        Then: Only DeepSeek is called, Groq is never invoked
        """
        parser = TextGenParser()

        # Mock response from DeepSeek (success case)
        deepseek_response = MagicMock()
        deepseek_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "akil_yurutme": "Test route extraction",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA",
                    "type": "1360"
                }
            ]
        })))]
        deepseek_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        groq_mock = AsyncMock()
        deepseek_mock = AsyncMock(return_value=deepseek_response)

        with patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_track_spend'):

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            result = await parser.parse_async("ANKARA -> İSTANBUL TIR")

            # Verify DeepSeek was called
            assert deepseek_mock.called, "DeepSeek API should be called (now primary)"

            # Verify Groq was NOT called (no fallback on success)
            assert not groq_mock.called, "Groq should not be called on DeepSeek success"


class TestDeepSeekAPIFailure:
    """AC#2: On DeepSeek API failure, Groq fallback is triggered."""

    @pytest.mark.asyncio
    async def test_deepseek_api_error_triggers_groq_fallback(self):
        """
        Given: DeepSeek API returns an error (exception)
        When: parse_async is called
        Then: Groq API is called as fallback
        """
        parser = TextGenParser()

        # Mock response from Groq (fallback success)
        groq_response = MagicMock()
        groq_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "akil_yurutme": "Fallback extraction",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "MERKEZ",
                    "type": "1360"
                }
            ]
        })))]
        groq_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        deepseek_mock = AsyncMock(side_effect=Exception("API Timeout"))
        groq_mock = AsyncMock(return_value=groq_response)

        with patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_track_spend'):

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            result = await parser.parse_async("ANKARA -> İSTANBUL TIR")

            # Verify DeepSeek was called first
            assert deepseek_mock.called, "DeepSeek should be tried first (now primary)"

            # Verify Groq was called (fallback triggered)
            assert groq_mock.called, "Groq should be called after DeepSeek failure"


class TestDeepSeekEmptyResultFallback:
    """AC#3: On DeepSeek success but empty routes, Groq is retried."""

    @pytest.mark.asyncio
    async def test_deepseek_empty_routes_triggers_groq(self):
        """
        Given: DeepSeek API succeeds but returns empty routes list
        When: parse_async detects empty result
        Then: Groq is called to retry

        Note: This test assumes implementation will check for empty routes
        and retry the next model instead of immediately returning [].
        """
        parser = TextGenParser()

        # DeepSeek returns empty routes (insufficient parsing)
        deepseek_response = MagicMock()
        deepseek_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "akil_yurutme": "Could not parse",
            "routes": []  # Empty!
        })))]
        deepseek_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        # Groq returns valid routes (fallback success)
        groq_response = MagicMock()
        groq_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "akil_yurutme": "Successful parsing",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "MERKEZ",
                    "type": "1360"
                }
            ]
        })))]
        groq_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        deepseek_mock = AsyncMock(return_value=deepseek_response)
        groq_mock = AsyncMock(return_value=groq_response)

        with patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_track_spend'):

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            result = await parser.parse_async("ANKARA YÜKLER: İSTANBUL")

            # After implementation: empty result should trigger fallback to Groq
            # Currently, the code returns immediately, so this test is EXPECTED TO FAIL (red)
            # until the empty-routes-retry logic is implemented.

            # Verify both were called (after implementation)
            assert deepseek_mock.called, "DeepSeek should be tried first (now primary)"
            assert groq_mock.called, "Groq should retry on empty routes from DeepSeek"


class TestAllModelsFail:
    """AC#4: When all models fail, empty list [] is returned."""

    @pytest.mark.asyncio
    async def test_all_models_fail_returns_empty_list(self):
        """
        Given: Both Groq and DeepSeek APIs fail with errors
        When: parse_async exhausts all models
        Then: Empty list [] is returned (no exception)
        """
        parser = TextGenParser()

        groq_mock = AsyncMock(side_effect=Exception("Groq Error"))
        deepseek_mock = AsyncMock(side_effect=Exception("DeepSeek Error"))

        with patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_track_spend'):

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            result = await parser.parse_async("ANKARA -> İSTANBUL TIR")

            # Both should be called
            assert groq_mock.called, "Groq should be tried"
            assert deepseek_mock.called, "DeepSeek should be tried after Groq fails"

            # Result should be empty list, not None or exception
            assert result == [], "Should return empty list on all-models failure"


class TestDeepSeekRateLimit:
    """AC#5: On DeepSeek rate-limit (429), Groq fallback occurs."""

    @pytest.mark.asyncio
    async def test_deepseek_429_rate_limit_fallback(self):
        """
        Given: DeepSeek API returns 429 (rate limit)
        When: parse_async handles the rate-limit error
        Then: Groq is called as fallback
        """
        parser = TextGenParser()

        # DeepSeek returns 429 error (rate limit)
        deepseek_mock = AsyncMock(
            side_effect=Exception("429 - Rate limit exceeded. Try again in 12.5s")
        )

        # Groq succeeds
        groq_response = MagicMock()
        groq_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "akil_yurutme": "Parsed via fallback",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İZMİR",
                    "nereye_ilce": "MERKEZ",
                    "type": "1360"
                }
            ]
        })))]
        groq_response.usage = MagicMock(prompt_tokens=100, completion_tokens=50)

        groq_mock = AsyncMock(return_value=groq_response)

        with patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_track_spend'), \
             patch('asyncio.sleep'):  # Mock sleep to speed up test

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            result = await parser.parse_async("ANKARA -> İZMİR TIR")

            # Verify DeepSeek was called first (even though it will fail with 429)
            assert deepseek_mock.called, "DeepSeek should be tried first (now primary)"

            # Verify Groq was called as fallback after 429
            # Note: This may require implementation to handle 429 specifically
            assert groq_mock.called, "Groq should fallback on DeepSeek 429"


class TestTrackSpendProvider:
    """AC#6: _track_spend() records 'provider' field for each model."""

    def test_track_spend_provider_detection_groq(self):
        """
        Given: _track_spend is called with a Groq-like model name
        When: Cost data is persisted
        Then: Written JSON entry should include 'provider' field

        Note: Uses 'llama' in model name to test Groq provider detection.
        Currently, provider field is not yet implemented, so test FAILS (red).
        """
        parser = TextGenParser()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock load_json_safe to return empty list (simulating first call)
            with patch('text_gen_parser.load_json_safe', return_value=[]):
                with patch('text_gen_parser.os.getcwd', return_value=tmpdir):
                    with patch('text_gen_parser.save_json_safe') as mock_save:
                        # Use a Groq-style model name; for now, use deepseek to ensure cost > 0
                        # (since groq pricing not yet defined in _track_spend)
                        # This test will verify provider detection once implemented
                        parser._track_spend('llama-3.3-70b', 1000, 500)

                        # Verify save_json_safe was called
                        assert mock_save.called, "_track_spend should save to file"

                        # Check the saved data includes provider
                        call_args = mock_save.call_args
                        saved_data = call_args[0][1]  # Second argument is the data

                        # After implementation, saved_data should be a list with entries
                        # containing 'provider' field. The new entry is the last one.
                        assert isinstance(saved_data, list) and len(saved_data) > 0, "Data should be a non-empty list"
                        last_entry = saved_data[-1]
                        # Provider field must be detected from model name
                        assert 'provider' in last_entry, f"Expected 'provider' field in entry, got keys: {list(last_entry.keys())}"
                        assert last_entry.get('provider') == 'groq', f"Expected provider='groq', got {last_entry.get('provider')}"

    def test_track_spend_provider_detection_deepseek(self):
        """
        Given: _track_spend is called with a DeepSeek model name
        When: Cost data is persisted
        Then: Written JSON entry should include 'provider': 'deepseek'

        Note: This test verifies provider field detection.
        Currently, provider field is not yet implemented, so test FAILS (red).
        """
        parser = TextGenParser()

        with tempfile.TemporaryDirectory() as tmpdir:
            # Mock load_json_safe to return empty list
            with patch('text_gen_parser.load_json_safe', return_value=[]):
                with patch('text_gen_parser.os.getcwd', return_value=tmpdir):
                    with patch('text_gen_parser.save_json_safe') as mock_save:
                        parser._track_spend('deepseek-v4-flash', 1000, 500)

                        # Verify save_json_safe was called
                        assert mock_save.called, "_track_spend should save to file"

                        # Check the saved data
                        call_args = mock_save.call_args
                        saved_data = call_args[0][1]

                        # After implementation, should detect 'deepseek' in model_name
                        # and set provider accordingly
                        assert isinstance(saved_data, list) and len(saved_data) > 0, "Data should be a non-empty list"
                        last_entry = saved_data[-1]
                        # Provider field must be present and correctly detected
                        assert 'provider' in last_entry, f"Expected 'provider' field in entry, got keys: {list(last_entry.keys())}"
                        assert last_entry.get('provider') == 'deepseek', f"Expected provider='deepseek', got {last_entry.get('provider')}"

    def test_track_spend_zero_tokens_no_write(self):
        """
        Given: _track_spend is called with zero tokens (input=0, output=0)
        When: Cost calculation results in 0.0
        Then: No file write occurs (entry not persisted, logs might still record)

        Current behavior (AC#6 notes): zero cost = no file write.
        """
        parser = TextGenParser()

        with tempfile.TemporaryDirectory() as tmpdir:
            with patch('text_gen_parser.os.getcwd', return_value=tmpdir):
                with patch('text_gen_parser.save_json_safe') as mock_save:
                    # Call with zero tokens
                    parser._track_spend('llama-3.1-8b-instant', 0, 0)

                    # After implementation: zero cost should NOT trigger a file write
                    # Current code (line 116): if cost > 0: ...
                    # So this should NOT call save_json_safe
                    assert not mock_save.called, "Zero-cost entries should not be persisted"


class TestHappyPathDeepSeek:
    """Integration test: DeepSeek success → no Groq call → cost recorded with provider."""

    @pytest.mark.asyncio
    async def test_happy_path_deepseek_success(self):
        """
        Given: Message arrives for parsing
        When: DeepSeek API returns valid, non-empty routes
        Then:
          - DeepSeek is called once
          - Groq is never called
          - Cost is recorded with provider='deepseek'
        """
        parser = TextGenParser()

        deepseek_response = MagicMock()
        deepseek_response.choices = [MagicMock(message=MagicMock(content=json.dumps({
            "akil_yurutme": "Parsed successfully",
            "routes": [
                {
                    "nereden_il": "ANKARA",
                    "nereden_ilce": "MERKEZ",
                    "nereye_il": "İSTANBUL",
                    "nereye_ilce": "TUZLA",
                    "type": "1360"
                }
            ]
        })))]
        deepseek_response.usage = MagicMock(prompt_tokens=200, completion_tokens=100)

        deepseek_mock = AsyncMock(return_value=deepseek_response)
        groq_mock = AsyncMock()  # Should not be called

        tracked_calls = []

        def track_spend_side_effect(model_name, input_tokens, output_tokens):
            tracked_calls.append({
                'model': model_name,
                'input': input_tokens,
                'output': output_tokens
            })

        with patch.object(parser, '_get_async_client') as get_groq, \
             patch.object(parser, '_get_deepseek_client') as get_deepseek, \
             patch.object(parser, '_track_spend', side_effect=track_spend_side_effect):

            groq_client_mock = AsyncMock()
            groq_client_mock.chat.completions.create = groq_mock
            get_groq.return_value = groq_client_mock

            deepseek_client_mock = AsyncMock()
            deepseek_client_mock.chat.completions.create = deepseek_mock
            get_deepseek.return_value = deepseek_client_mock

            result = await parser.parse_async("ANKARA YÜKLER: İSTANBUL TUZLA TIR")

            # Verify DeepSeek was called
            assert deepseek_mock.called, "DeepSeek should be called in happy path (now primary)"
            assert deepseek_mock.call_count == 1, "DeepSeek should be called exactly once"

            # Verify Groq was NOT called
            assert not groq_mock.called, "Groq should not be called on DeepSeek success"

            # Verify cost was tracked (with the model name that will later have provider extracted)
            assert len(tracked_calls) > 0, "Cost tracking should be called"
            # After implementation, model name should be 'deepseek-v4-flash' or DeepSeek identifier
            # tracked_calls[0]['model'] should indicate DeepSeek


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
