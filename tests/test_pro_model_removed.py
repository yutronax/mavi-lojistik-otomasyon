#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for baileys-pro-model-kaldir-ve-blacklist-lid-fix.

Acceptance Criteria:
1. [Critical] Given `text_gen_parser.py`'nin model fallback zinciri, When
   `deepseek-v4-flash` (birincil model) başarısız olur, Then sıradaki
   deneme doğrudan Groq (`openai/gpt-oss-20b`) olmalı — `deepseek-v4-pro`
   zincirde HİÇ görünmemeli.
2. [Critical] Given `self.fallback_models` attribute'u, When kod okunur,
   Then boş liste (`[]`) olmalı — `deepseek-v4-pro` string'i kod tabanında
   hiçbir yerde geçmemeli.
6. [Medium] Given `deepseek-v4-flash` VE Groq (`openai/gpt-oss-20b`) İKİSİ
   DE başarısız olur (pro artık yok), When bu durum oluşur, Then mevcut
   "tüm modeller tükendi" hata davranışı (retry/log, mevcut kod)
   DEĞİŞMEDEN korunmalı — bu bir regresyon testi.
"""

import pytest
import os
import sys
import inspect
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out problematic imports BEFORE importing TextGenParser
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

# NOW safe to import TextGenParser
from text_gen_parser import TextGenParser


class TestProModelRemoved:
    """
    AC-1, AC-2, AC-6: Verify pro model is completely removed from fallback chain
    and all-models-exhausted behavior is preserved.
    """

    def test_fallback_models_is_empty_list(self):
        """
        AC-2: Given `self.fallback_models` attribute'u, When kod okunur,
        Then boş liste (`[]`) olmalı.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()
            assert isinstance(parser.fallback_models, list), \
                "fallback_models should be a list"
            assert parser.fallback_models == [], \
                f"fallback_models should be empty [], got {parser.fallback_models}"

    def test_no_pro_model_in_source_code(self):
        """
        AC-2: Given `text_gen_parser.py`'nin kaynak kodu, When okunur,
        Then `deepseek-v4-pro` string'i hiçbir yerde geçmemeli.
        """
        # Read the source file directly
        source_file = os.path.join(os.path.dirname(__file__), '..', 'text_gen_parser.py')
        assert os.path.exists(source_file), f"text_gen_parser.py not found at {source_file}"

        with open(source_file, 'r', encoding='utf-8') as f:
            source_code = f.read()

        assert 'deepseek-v4-pro' not in source_code, \
            "Source code should not contain 'deepseek-v4-pro' string anywhere"

    def test_models_to_try_chain_without_pro(self):
        """
        AC-1: Given `text_gen_parser.py`'nin model fallback zinciri satır 463,
        When parse_async() çalışır, Then fallback zinciri
        `[model_robust] + fallback_models + ['openai/gpt-oss-20b']`
        otomatik olarak `['deepseek-v4-flash', 'openai/gpt-oss-20b']` olmalı
        (pro yok, flash ve groq sadece).

        Verification: Parse the source code to extract models_to_try chain logic.
        """
        # Read source code to verify the logic
        source_file = os.path.join(os.path.dirname(__file__), '..', 'text_gen_parser.py')
        with open(source_file, 'r', encoding='utf-8') as f:
            source_code = f.read()

        # Verify the line exists with the expected pattern
        assert 'models_to_try = [self.model_robust] + self.fallback_models + [\'openai/gpt-oss-20b\']' in source_code, \
            "models_to_try chain not found or has unexpected format"

        # Verify that fallback_models is empty, making the chain just [flash, groq]
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()
            expected_models = [parser.model_robust] + parser.fallback_models + ['openai/gpt-oss-20b']
            expected_models = list(dict.fromkeys(expected_models))  # Deduplicate

            assert expected_models == ['deepseek-v4-flash', 'openai/gpt-oss-20b'], \
                f"Expected [flash, groq], got {expected_models}"

    @pytest.mark.asyncio
    async def test_parse_async_all_models_exhausted_behavior(self):
        """
        AC-6: Given flash VE Groq ikisi de başarısız olur (pro artık yok),
        When bu durum oluşur, Then mevcut "tüm modeller tükendi" hata davranışı
        (return [] + log error, mevcut kod) DEĞİŞMEDEN korunmalı.

        Regresyon test: Verify that parse_async() returns [] (not raises exception)
        when all models fail. This should still be true after pro removal.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()

            # Mock all model clients to fail
            async def async_exception(*args, **kwargs):
                raise Exception("Model API error")

            with patch.object(parser, '_get_deepseek_client') as mock_ds:
                with patch.object(parser, '_get_async_client') as mock_groq:
                    # Setup mocks
                    mock_ds_client = MagicMock()
                    mock_ds_client.chat.completions.create = AsyncMock(side_effect=async_exception)
                    mock_ds_client.__aenter__ = AsyncMock(return_value=mock_ds_client)
                    mock_ds_client.__aexit__ = AsyncMock(return_value=False)
                    mock_ds_client.close = AsyncMock()
                    mock_ds.return_value = mock_ds_client

                    mock_groq_client = MagicMock()
                    mock_groq_client.chat.completions.create = AsyncMock(side_effect=async_exception)
                    mock_groq_client.__aenter__ = AsyncMock(return_value=mock_groq_client)
                    mock_groq_client.__aexit__ = AsyncMock(return_value=False)
                    mock_groq_client.close = AsyncMock()
                    mock_groq.return_value = mock_groq_client

                    # Call parse_async
                    result = await parser.parse_async("test message")

                    # Verify behavior: should return [] (not raise exception)
                    assert isinstance(result, list), \
                        "parse_async should return a list, not raise exception"
                    assert result == [], \
                        "parse_async should return empty list when all models fail"

    def test_parse_async_method_exists(self):
        """
        Utility test: Verify parse_async method exists and is callable.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()
            assert hasattr(parser, 'parse_async'), \
                "TextGenParser should have parse_async method"
            assert callable(parser.parse_async), \
                "parse_async should be callable"

    def test_model_robust_is_flash(self):
        """
        Utility test: Verify that the primary model is still deepseek-v4-flash.
        """
        with patch.dict(os.environ, {'DEEPSEEK_API_KEY': 'test_key'}):
            parser = TextGenParser()
            assert parser.model_robust == 'deepseek-v4-flash', \
                f"Primary model should be deepseek-v4-flash, got {parser.model_robust}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
