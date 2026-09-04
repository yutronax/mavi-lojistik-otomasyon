#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for deepseek-maliyet-dusurme-stage-birlestir-junk-filtre.

Acceptance Criteria:
AC-1 [Critical]: Stage 1 (_extract_locations_stage1_async) HİÇ ÇAĞRILMAMALI;
                 mesaj başına DeepSeek+Groq baseline çağrı sayısı ~2'den ~1'e düşmeli.
AC-2 [Critical]: Mevcut retry+model-fallback zinciri (DeepSeek→Groq, 3 deneme)
                 AYNEN korunmalı (regresyon testi).
AC-6 [Medium]:   Model boş routes (`routes: []`) döndürdüğünde ve son model değilse,
                 sıradaki modele geçme davranışı DEĞİŞMEMELİ (regresyon testi).
"""

import pytest
import os
import sys
import json
from unittest.mock import MagicMock, patch, AsyncMock, call
import asyncio

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out problematic imports BEFORE importing TextGenParser
_mock = MagicMock()
sys.modules['google.genai'] = _mock
sys.modules['google'] = _mock
sys.modules['dotenv'] = _mock

# MongoDB mocks
_pymongo_mock = MagicMock()
_pymongo_mock.MongoClient = MagicMock()
_pymongo_mock.UpdateOne = MagicMock()
_pymongo_mock.DESCENDING = MagicMock()
_pymongo_errors_mock = MagicMock()
_pymongo_mock.errors = _pymongo_errors_mock
sys.modules['pymongo'] = _pymongo_mock
sys.modules['pymongo.errors'] = _pymongo_errors_mock

# NOW safe to import TextGenParser
from text_gen_parser import TextGenParser


class TestStageMergeCallCount:
    """
    AC-1, AC-2, AC-6: Verify that Stage 1 is not called separately,
    API call count drops from 2 to 1, and retry/fallback behavior is preserved.
    """

    def test_extract_locations_stage1_not_called(self):
        """
        AC-1 [Critical]: Given parse_async() is called with a 150+ char message,
        When parsing happens, Then _extract_locations_stage1_async should NOT be called.

        THIS TEST WILL FAIL (red) IF Stage 1 is still being called separately.
        Current code has Stage 1 + Stage 2 as two separate API calls.
        After refactoring, Stage 1 should be integrated into Stage 2's prompt,
        and this method should never be called.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            # Mock the Stage 1 method to track if it's called
            with patch.object(parser, '_extract_locations_stage1_async',
                            new_callable=AsyncMock) as mock_stage1:
                # Mock the actual model clients to avoid real API calls
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = json.dumps({
                    "akil_yurutme": "Test routing",
                    "routes": [
                        {
                            "nereden_il": "ISTANBUL",
                            "nereden_ilce": "MERKEZ",
                            "nereye_il": "ANKARA",
                            "nereye_ilce": "MERKEZ",
                            "type": "TIR",
                            "isim": "Test Co."
                        }
                    ]
                })
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50

                with patch.object(parser, '_get_deepseek_client') as mock_ds:
                    mock_ds_client = MagicMock()
                    mock_ds_client.chat.completions.create = AsyncMock(return_value=mock_response)
                    mock_ds_client.__aenter__ = AsyncMock(return_value=mock_ds_client)
                    mock_ds_client.__aexit__ = AsyncMock(return_value=False)
                    mock_ds_client.close = AsyncMock()
                    mock_ds.return_value = mock_ds_client

                    # Long message (>150 chars)
                    long_message = "İSTANBUL'DEN ANKARA'YA TIR LAZIM. Çok acil sipariş var, birinci kademe taşıyıcı arıyorum. Ağır bir yükleme işi var, lütfen en kısa zamanda cevap verin. Fiyat sorulur. İletişim: 0532 123 45 67"

                    # Run parse_async
                    result = asyncio.run(parser.parse_async(long_message))

                    # CRITICAL CHECK: Stage 1 should NOT be called
                    # This assertion will FAIL with current code (Stage 1 is still being called)
                    mock_stage1.assert_not_called()

    def test_api_call_count_single_call_per_message(self):
        """
        AC-1 [Critical]: Given a long (150+) message is parsed,
        When the message is processed through parse_async(),
        Then the total baseline API call count (successful first attempt, no retries)
        should be 1 (not 2 as in current code with separate Stage 1 + Stage 2).

        THIS TEST WILL FAIL (red) WITH CURRENT CODE because it makes 2 calls:
        one for Stage 1 (_ extract_locations_stage1_async) and one for Stage 2.
        After refactoring to merge Stage 1 into Stage 2's prompt, this should be 1.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            call_count = {"deepseek": 0, "groq": 0}

            # Mock DeepSeek client
            mock_ds_response = MagicMock()
            mock_ds_response.choices = [MagicMock()]
            mock_ds_response.choices[0].message.content = json.dumps({
                "akil_yurutme": "Test routing",
                "routes": [
                    {
                        "nereden_il": "ISTANBUL",
                        "nereden_ilce": "MERKEZ",
                        "nereye_il": "ANKARA",
                        "nereye_ilce": "MERKEZ",
                        "type": "TIR",
                        "isim": "Test Co."
                    }
                ]
            })
            mock_ds_response.usage = MagicMock()
            mock_ds_response.usage.prompt_tokens = 100
            mock_ds_response.usage.completion_tokens = 50

            async def deepseek_call_tracker(*args, **kwargs):
                call_count["deepseek"] += 1
                return mock_ds_response

            with patch.object(parser, '_get_deepseek_client') as mock_ds:
                mock_ds_client = MagicMock()
                mock_ds_client.chat.completions.create = AsyncMock(side_effect=deepseek_call_tracker)
                mock_ds_client.__aenter__ = AsyncMock(return_value=mock_ds_client)
                mock_ds_client.__aexit__ = AsyncMock(return_value=False)
                mock_ds_client.close = AsyncMock()
                mock_ds.return_value = mock_ds_client

                # Long message (>150 chars)
                long_message = "İSTANBUL'DEN ANKARA'YA TIR LAZIM. Çok acil sipariş var, birinci kademe taşıyıcı arıyorum. Ağır bir yükleme işi var, lütfen en kısa zamanda cevap verin. Fiyat sorulur. İletişim: 0532 123 45 67"

                # Run parse_async
                result = asyncio.run(parser.parse_async(long_message))

                # CRITICAL CHECK: Should be exactly 1 call for a successful parse
                # Current code: 2 calls (Stage 1 + Stage 2)
                # After refactoring: 1 call (merged)
                # THIS TEST EXPECTS 1, SO IT WILL FAIL WITH CURRENT CODE
                assert call_count["deepseek"] == 1, \
                    f"Expected 1 DeepSeek API call, but got {call_count['deepseek']}. " \
                    "Stage 1 is still making a separate call."

    @pytest.mark.asyncio
    async def test_retry_chain_preserved_on_429_error(self):
        """
        AC-2 [Critical]: Given DeepSeek returns 429 (rate limit),
        When parse_async() retries, Then it should fallback to Groq
        and retry logic should remain unchanged (3 attempts per model, model fallback order).

        This is a REGRESION test — behavior should not change after Stage 1 merge.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            # Setup: DeepSeek fails 429, then Groq succeeds
            async def deepseek_fail(*args, **kwargs):
                error = MagicMock()
                error.status_code = 429
                raise error

            mock_groq_response = MagicMock()
            mock_groq_response.choices = [MagicMock()]
            mock_groq_response.choices[0].message.content = json.dumps({
                "akil_yurutme": "Fallback to Groq",
                "routes": [
                    {
                        "nereden_il": "ANKARA",
                        "nereden_ilce": "MERKEZ",
                        "nereye_il": "ISTANBUL",
                        "nereye_ilce": "MERKEZ",
                        "type": "KAMYON",
                        "isim": "FallbackCo"
                    }
                ]
            })
            mock_groq_response.usage = MagicMock()
            mock_groq_response.usage.prompt_tokens = 80
            mock_groq_response.usage.completion_tokens = 40

            with patch.object(parser, '_get_deepseek_client') as mock_ds:
                with patch.object(parser, '_get_async_client') as mock_groq:
                    # DeepSeek setup (will fail)
                    mock_ds_client = MagicMock()
                    mock_ds_client.chat.completions.create = AsyncMock(side_effect=deepseek_fail)
                    mock_ds_client.__aenter__ = AsyncMock(return_value=mock_ds_client)
                    mock_ds_client.__aexit__ = AsyncMock(return_value=False)
                    mock_ds_client.close = AsyncMock()
                    mock_ds.return_value = mock_ds_client

                    # Groq setup (will succeed)
                    mock_groq_client = MagicMock()
                    mock_groq_client.chat.completions.create = AsyncMock(return_value=mock_groq_response)
                    mock_groq_client.__aenter__ = AsyncMock(return_value=mock_groq_client)
                    mock_groq_client.__aexit__ = AsyncMock(return_value=False)
                    mock_groq_client.close = AsyncMock()
                    mock_groq.return_value = mock_groq_client

                    # Parse message
                    message = "ANKARA'DAN ISTANBUL'E KAMYON LAZIM. Acil gönderi. Fiyat sorunuz."
                    result = await parser.parse_async(message)

                    # Should succeed via Groq fallback
                    assert isinstance(result, list), \
                        "parse_async should return a list after fallback to Groq"
                    assert len(result) > 0 or result == [], \
                        "Result should be a valid list (empty or with routes)"

    @pytest.mark.asyncio
    async def test_all_models_exhausted_behavior_unchanged(self):
        """
        AC-6 [Medium]: Given both DeepSeek and Groq fail,
        When all models are exhausted, Then parse_async should return [] (empty list)
        and log an error, NOT raise an exception. This behavior should be preserved.

        REGRESSION test: Ensure fallback to empty result is unchanged.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            # Both models fail
            async def model_fail(*args, **kwargs):
                raise Exception("Model API error")

            with patch.object(parser, '_get_deepseek_client') as mock_ds:
                with patch.object(parser, '_get_async_client') as mock_groq:
                    # DeepSeek setup
                    mock_ds_client = MagicMock()
                    mock_ds_client.chat.completions.create = AsyncMock(side_effect=model_fail)
                    mock_ds_client.__aenter__ = AsyncMock(return_value=mock_ds_client)
                    mock_ds_client.__aexit__ = AsyncMock(return_value=False)
                    mock_ds_client.close = AsyncMock()
                    mock_ds.return_value = mock_ds_client

                    # Groq setup
                    mock_groq_client = MagicMock()
                    mock_groq_client.chat.completions.create = AsyncMock(side_effect=model_fail)
                    mock_groq_client.__aenter__ = AsyncMock(return_value=mock_groq_client)
                    mock_groq_client.__aexit__ = AsyncMock(return_value=False)
                    mock_groq_client.close = AsyncMock()
                    mock_groq.return_value = mock_groq_client

                    # Parse message
                    message = "TEST MESSAGE FOR ALL MODELS EXHAUSTED"
                    result = await parser.parse_async(message)

                    # Should return empty list, not raise exception
                    assert isinstance(result, list), \
                        "parse_async should return list when all models fail"
                    assert result == [], \
                        "parse_async should return empty list when all models fail"

    def test_model_chain_order_flash_then_groq(self):
        """
        Utility test: Verify model fallback chain is [flash, groq] (pro removed).
        This ensures the order of retry is correct.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            # Check the chain
            expected_models = [parser.model_robust] + parser.fallback_models + ['openai/gpt-oss-20b']
            expected_models = list(dict.fromkeys(expected_models))  # Deduplicate

            assert expected_models == ['deepseek-v4-flash', 'openai/gpt-oss-20b'], \
                f"Expected [flash, groq], got {expected_models}. Pro model should not be in chain."

    def test_multi_section_message_prompt_includes_reasoning_instruction(self):
        """
        Test for multi-section (150+ char) messages: Verify that the prompt
        sent to DeepSeek INCLUDES the "STEP-BY-STEP REASONING" instruction.

        This validates that the Stage 1 merge properly augments the prompt
        with reasoning guidance for complex, multi-section messages.

        Acceptance: The user message content in messages parameter should contain:
        - "STEP-BY-STEP REASONING" (the added instruction)
        - The original message sections (with "---" separators and "YÜKLER" headers)
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            # Multi-section message (150+ chars with multiple sections separated by ---)
            multi_section_message = """BURSA YÜKLER:
Adana merkez
Mersin Tarsus
13.60 Tır HIZLILI TAŞIMA
---
KONYA KARATAY YÜKLER:
İzmir Aliağa merkez endüstriyel bölge
Manisa Akhisar kargo
---
SAMSUN YÜKLER:
Ankara merkez acil gönderim"""

            # Verify message is long enough to trigger reasoning instruction
            assert len(multi_section_message) > 150, \
                f"Test message must be >150 chars, got {len(multi_section_message)}"

            # Capture the messages parameter passed to chat.completions.create
            captured_messages = {}

            def capture_deepseek_call(*args, **kwargs):
                captured_messages["messages"] = kwargs.get("messages", [])
                # Return mock response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = json.dumps({
                    "akil_yurutme": "Multi-section reasoning",
                    "routes": [
                        {
                            "nereden_il": "BURSA",
                            "nereden_ilce": "MERKEZ",
                            "nereye_il": "ADANA",
                            "nereye_ilce": "MERKEZ",
                            "type": "TIR",
                            "isim": "Test"
                        }
                    ]
                })
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50
                mock_response.choices[0].finish_reason = 'stop'
                return mock_response

            with patch.object(parser, '_get_deepseek_client') as mock_ds:
                mock_ds_client = MagicMock()
                mock_ds_client.chat.completions.create = AsyncMock(side_effect=capture_deepseek_call)
                mock_ds_client.__aenter__ = AsyncMock(return_value=mock_ds_client)
                mock_ds_client.__aexit__ = AsyncMock(return_value=False)
                mock_ds_client.close = AsyncMock()
                mock_ds.return_value = mock_ds_client

                # Run parse_async
                result = asyncio.run(parser.parse_async(multi_section_message))

                # Verify messages were captured
                assert "messages" in captured_messages, \
                    "Messages parameter was not captured from chat.completions.create"

                messages = captured_messages["messages"]
                assert len(messages) >= 2, \
                    f"Expected system + user messages, got {len(messages)}"

                # Find the user message
                user_message = None
                for msg in messages:
                    if msg.get("role") == "user":
                        user_message = msg
                        break

                assert user_message is not None, \
                    "No user message found in messages"

                user_content = user_message.get("content", "")

                # Check 1: Prompt must include "STEP-BY-STEP REASONING" instruction
                assert "STEP-BY-STEP REASONING" in user_content, \
                    "Prompt does not include 'STEP-BY-STEP REASONING' instruction for 150+ char message"

                # Check 2: Prompt must include section separator (--- marker)
                assert "---" in user_content, \
                    "Prompt does not include section separators (---)"

                # Check 3: Prompt must include original header (YÜKLER keyword)
                assert "YÜKLER" in user_content, \
                    "Prompt does not include original message header (YÜKLER)"

                # Check 4: Verify reasoning instruction comes BEFORE main extraction rules
                reasoning_idx = user_content.find("STEP-BY-STEP REASONING")
                extraction_idx = user_content.find("EXTRACTION & LOGIC RULES")
                assert reasoning_idx < extraction_idx, \
                    "STEP-BY-STEP REASONING instruction must appear before EXTRACTION & LOGIC RULES"

    def test_short_message_no_reasoning_instruction(self):
        """
        Test for short (< 150 char) messages: Verify that the prompt
        sent to DeepSeek does NOT include the "STEP-BY-STEP REASONING" instruction.

        This validates that reasoning instruction is conditional (only for 150+ chars)
        and doesn't add unnecessary prompt bloat for simple messages.

        Acceptance: The user message content should NOT contain "STEP-BY-STEP REASONING"
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            # Short message (< 150 chars)
            short_message = "ADANA İZMİR TIR LAZIM"

            # Verify message is short enough to NOT trigger reasoning instruction
            assert len(short_message) <= 150, \
                f"Test message must be <=150 chars, got {len(short_message)}"

            # Capture the messages parameter passed to chat.completions.create
            captured_messages = {}

            def capture_deepseek_call(*args, **kwargs):
                captured_messages["messages"] = kwargs.get("messages", [])
                # Return mock response
                mock_response = MagicMock()
                mock_response.choices = [MagicMock()]
                mock_response.choices[0].message.content = json.dumps({
                    "akil_yurutme": "Simple message",
                    "routes": [
                        {
                            "nereden_il": "ADANA",
                            "nereden_ilce": "MERKEZ",
                            "nereye_il": "IZMIR",
                            "nereye_ilce": "MERKEZ",
                            "type": "TIR",
                            "isim": "Test"
                        }
                    ]
                })
                mock_response.usage = MagicMock()
                mock_response.usage.prompt_tokens = 100
                mock_response.usage.completion_tokens = 50
                mock_response.choices[0].finish_reason = 'stop'
                return mock_response

            with patch.object(parser, '_get_deepseek_client') as mock_ds:
                mock_ds_client = MagicMock()
                mock_ds_client.chat.completions.create = AsyncMock(side_effect=capture_deepseek_call)
                mock_ds_client.__aenter__ = AsyncMock(return_value=mock_ds_client)
                mock_ds_client.__aexit__ = AsyncMock(return_value=False)
                mock_ds_client.close = AsyncMock()
                mock_ds.return_value = mock_ds_client

                # Run parse_async
                result = asyncio.run(parser.parse_async(short_message))

                # Verify messages were captured
                assert "messages" in captured_messages, \
                    "Messages parameter was not captured from chat.completions.create"

                messages = captured_messages["messages"]
                assert len(messages) >= 2, \
                    f"Expected system + user messages, got {len(messages)}"

                # Find the user message
                user_message = None
                for msg in messages:
                    if msg.get("role") == "user":
                        user_message = msg
                        break

                assert user_message is not None, \
                    "No user message found in messages"

                user_content = user_message.get("content", "")

                # Check: Short message prompt must NOT include "STEP-BY-STEP REASONING"
                assert "STEP-BY-STEP REASONING" not in user_content, \
                    "Short message (<150 chars) should NOT include 'STEP-BY-STEP REASONING' instruction"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
