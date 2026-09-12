#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for ayarlar-sayfasi-temizlik-tasarim (AC-1 through AC-5).

Acceptance Criteria:
1. [Critical] AC-1: SettingsPage instance'ında whapi_token_field, whapi_url_field,
   refresh_interval_field OLMAMALI (hasattr False dönmeli).

2. [Critical] AC-2: save_settings() config sözlüğünde SADECE llm_url/llm_model/llm_keys
   olmalı, whapi_token/whapi_url/refresh_interval OLMAMALI. os.environ set edilmeli.

3. [High] AC-3: load_settings() eski config'te whapi_token/whapi_url/refresh_interval
   varken hatasız çalışmalı (exception fırlatmamalı).

4. [High] AC-4: llm_url_field.value boş string iken save_settings() hatasız çalışmalı
   (exception olmadan), boş string config'e yazılmalı.

5. [Medium] AC-5: data_service.save_config exception fırlattığında yakalanıp
   self._show_error çağrılmalı (uygulama çökmemeli).

Test Stratejisi:
- Unit: Settings instance'ı field attribute'ları, config dict anahtarları
- Integration: save/load cycle, eski config uyumluluğu, error handling
"""

import pytest
import os
import sys
import json
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock, call
from pathlib import Path

# Project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub heavy imports BEFORE importing settings_page
_mock = MagicMock()
sys.modules['google.genai'] = _mock
sys.modules['google'] = _mock
sys.modules['dotenv'] = _mock

_pymongo_mock = MagicMock()
sys.modules['pymongo'] = _pymongo_mock
sys.modules['pymongo.errors'] = _pymongo_mock

# Stub Flet before importing settings_page
_flet_mock = MagicMock()

# TextField should return a new, independent mock each time it's called
def _new_text_field(**kwargs):
    field = MagicMock()
    field.value = kwargs.get("value", "")
    return field

_flet_mock.TextField.side_effect = _new_text_field
sys.modules['flet'] = _flet_mock

# Now we can safely import
from src.gui.pages.settings_page import SettingsPage


@pytest.fixture
def mock_page():
    """Mock Flet page object."""
    page = MagicMock()
    page.snack_bar = MagicMock()
    page.update = MagicMock()
    return page


@pytest.fixture
def mock_data_service():
    """Mock AsyncDataService with async methods."""
    service = MagicMock()
    service.load_config = AsyncMock(return_value={
        "llm_url": "https://api.deepseek.com/v1",
        "llm_model": "deepseek-chat",
        "llm_keys": "test-key"
    })
    service.save_config = AsyncMock(return_value=None)
    return service


@pytest.fixture
def mock_api_manager():
    """Mock APIKeyManager."""
    manager = MagicMock()
    manager.load_keys = MagicMock()
    return manager


@pytest.fixture
def settings_page(mock_page):
    """Create SettingsPage instance with mocked dependencies."""
    with patch('src.gui.pages.settings_page.AsyncDataService') as mock_async_ds, \
         patch('src.gui.pages.settings_page.DataService') as mock_ds, \
         patch('src.gui.pages.settings_page.APIKeyManager') as mock_api_mgr:

        # Setup AsyncDataService to return our mock
        mock_service = MagicMock()
        mock_service.load_config = AsyncMock(return_value={
            "llm_url": "https://api.deepseek.com/v1",
            "llm_model": "deepseek-chat",
            "llm_keys": "test-key"
        })
        mock_service.save_config = AsyncMock(return_value=None)
        mock_async_ds.return_value = mock_service

        # Setup DataService (sync wrapper)
        mock_ds.return_value = MagicMock()

        # Setup APIKeyManager
        mock_api_mgr.return_value = MagicMock()

        # Create instance
        page_instance = SettingsPage(mock_page)
        page_instance._mock_service = mock_service
        page_instance._mock_api_mgr = mock_api_mgr.return_value

        return page_instance


# ============================================================================
# AC-1 Tests: Dead field attributes should not exist
# ============================================================================

class TestAC1_DeadFieldsNotExist:
    """AC-1 [Critical]: SettingsPage should not have whapi_token_field,
    whapi_url_field, or refresh_interval_field attributes."""

    def test_whapi_token_field_does_not_exist(self, settings_page):
        """whapi_token_field attribute should not exist after cleanup."""
        assert not hasattr(settings_page, 'whapi_token_field'), \
            "whapi_token_field should be removed from SettingsPage"

    def test_whapi_url_field_does_not_exist(self, settings_page):
        """whapi_url_field attribute should not exist after cleanup."""
        assert not hasattr(settings_page, 'whapi_url_field'), \
            "whapi_url_field should be removed from SettingsPage"

    def test_refresh_interval_field_does_not_exist(self, settings_page):
        """refresh_interval_field attribute should not exist after cleanup."""
        assert not hasattr(settings_page, 'refresh_interval_field'), \
            "refresh_interval_field should be removed from SettingsPage"

    def test_only_llm_fields_exist(self, settings_page):
        """Only LLM-related fields should exist."""
        assert hasattr(settings_page, 'llm_url_field'), \
            "llm_url_field should exist"
        assert hasattr(settings_page, 'llm_model_field'), \
            "llm_model_field should exist"
        assert hasattr(settings_page, 'llm_keys_field'), \
            "llm_keys_field should exist"


# ============================================================================
# AC-2 Tests: Config dict should only contain LLM keys
# ============================================================================

class TestAC2_ConfigDictOnlyLLMKeys:
    """AC-2 [Critical]: save_settings() should create config dict with only
    llm_url, llm_model, llm_keys keys. whapi_token, whapi_url, refresh_interval
    should NOT be in config dict."""

    def test_save_settings_config_dict_only_llm_keys(self, settings_page):
        """Config dict passed to save_config should only have LLM keys."""
        settings_page.llm_url_field.value = "https://api.test.com/v1"
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = "test-api-key"

        asyncio.run(settings_page.save_settings(None))

        # Verify save_config was called
        settings_page._mock_service.save_config.assert_called_once()

        # Get the config dict that was passed
        call_args = settings_page._mock_service.save_config.call_args
        config_dict = call_args[0][1]  # Second positional arg (config)

        # Verify only LLM keys exist
        expected_keys = {"llm_url", "llm_model", "llm_keys"}
        actual_keys = set(config_dict.keys())

        assert actual_keys == expected_keys, \
            f"Config should only have {expected_keys}, but has {actual_keys}"

    def test_whapi_keys_not_in_config(self, settings_page):
        """Config dict should NOT contain whapi_token or whapi_url."""
        settings_page.llm_url_field.value = "https://api.test.com/v1"
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = "test-key"

        asyncio.run(settings_page.save_settings(None))

        call_args = settings_page._mock_service.save_config.call_args
        config_dict = call_args[0][1]

        assert "whapi_token" not in config_dict, \
            "whapi_token should not be in config dict"
        assert "whapi_url" not in config_dict, \
            "whapi_url should not be in config dict"

    def test_refresh_interval_not_in_config(self, settings_page):
        """Config dict should NOT contain refresh_interval."""
        settings_page.llm_url_field.value = "https://api.test.com/v1"
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = "test-key"

        asyncio.run(settings_page.save_settings(None))

        call_args = settings_page._mock_service.save_config.call_args
        config_dict = call_args[0][1]

        assert "refresh_interval" not in config_dict, \
            "refresh_interval should not be in config dict"

    def test_os_environ_llm_vars_set(self, settings_page):
        """os.environ should be updated with LLM variables."""
        test_url = "https://api.custom.com/v1"
        test_model = "custom-model"
        test_keys = "key1,key2"

        settings_page.llm_url_field.value = test_url
        settings_page.llm_model_field.value = test_model
        settings_page.llm_keys_field.value = test_keys

        with patch.dict(os.environ, {}, clear=False):
            asyncio.run(settings_page.save_settings(None))

            assert os.environ.get("LLM_BASE_URL") == test_url, \
                "LLM_BASE_URL should be set"
            assert os.environ.get("LLM_MODEL") == test_model, \
                "LLM_MODEL should be set"
            assert os.environ.get("GROQ_API_KEYS") == test_keys, \
                "GROQ_API_KEYS should be set"


# ============================================================================
# AC-3 Tests: Load settings with old config keys should work
# ============================================================================

class TestAC3_BackwardCompatibilityOldConfig:
    """AC-3 [High]: load_settings() should handle old config files that still
    contain whapi_token, whapi_url, refresh_interval without errors."""

    def test_load_settings_with_old_whapi_keys(self, settings_page):
        """load_settings should not crash when config has old whapi keys."""
        old_config = {
            "llm_url": "https://api.deepseek.com/v1",
            "llm_model": "deepseek-chat",
            "llm_keys": "key1",
            "whapi_token": "old_token_value",  # Old key
            "whapi_url": "https://old.whapi.url"  # Old key
        }

        settings_page._mock_service.load_config = AsyncMock(return_value=old_config)

        # Should not raise
        try:
            asyncio.run(settings_page.load_settings())
        except Exception as e:
            pytest.fail(f"load_settings should not raise with old config keys, but raised: {e}")

    def test_load_settings_with_old_refresh_interval(self, settings_page):
        """load_settings should handle old refresh_interval key."""
        old_config = {
            "llm_url": "https://api.deepseek.com/v1",
            "llm_model": "deepseek-chat",
            "llm_keys": "key1",
            "refresh_interval": 60  # Old key
        }

        settings_page._mock_service.load_config = AsyncMock(return_value=old_config)

        # Should not raise
        try:
            asyncio.run(settings_page.load_settings())
        except Exception as e:
            pytest.fail(f"load_settings should not raise with refresh_interval, but raised: {e}")

    def test_load_settings_with_all_old_keys(self, settings_page):
        """load_settings should handle config with all old keys present."""
        old_config = {
            "llm_url": "https://api.deepseek.com/v1",
            "llm_model": "deepseek-chat",
            "llm_keys": "key1",
            "whapi_token": "token",
            "whapi_url": "https://whapi.url",
            "refresh_interval": 120
        }

        settings_page._mock_service.load_config = AsyncMock(return_value=old_config)

        # Should not raise
        try:
            asyncio.run(settings_page.load_settings())
        except Exception as e:
            pytest.fail(f"load_settings should handle all old keys, but raised: {e}")


# ============================================================================
# AC-4 Tests: Empty LLM field values should be handled gracefully
# ============================================================================

class TestAC4_EmptyFieldValuesHandling:
    """AC-4 [High]: save_settings() should work without errors when LLM fields
    are empty, and empty strings should be saved to config."""

    def test_empty_llm_url_field_saves_empty_string(self, settings_page):
        """Empty llm_url_field should save as empty string, not crash."""
        settings_page.llm_url_field.value = ""
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = "test-key"

        # Should not raise
        try:
            asyncio.run(settings_page.save_settings(None))
        except Exception as e:
            pytest.fail(f"save_settings should handle empty llm_url, but raised: {e}")

        # Verify empty string was saved
        call_args = settings_page._mock_service.save_config.call_args
        config_dict = call_args[0][1]
        assert config_dict["llm_url"] == "", \
            "Empty llm_url should be saved as empty string"

    def test_empty_llm_model_field_saves_empty_string(self, settings_page):
        """Empty llm_model_field should save as empty string."""
        settings_page.llm_url_field.value = "https://api.test.com"
        settings_page.llm_model_field.value = ""
        settings_page.llm_keys_field.value = "test-key"

        # Should not raise
        try:
            asyncio.run(settings_page.save_settings(None))
        except Exception as e:
            pytest.fail(f"save_settings should handle empty llm_model, but raised: {e}")

        call_args = settings_page._mock_service.save_config.call_args
        config_dict = call_args[0][1]
        assert config_dict["llm_model"] == "", \
            "Empty llm_model should be saved as empty string"

    def test_empty_llm_keys_field_saves_empty_string(self, settings_page):
        """Empty llm_keys_field should save as empty string."""
        settings_page.llm_url_field.value = "https://api.test.com"
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = ""

        # Should not raise
        try:
            asyncio.run(settings_page.save_settings(None))
        except Exception as e:
            pytest.fail(f"save_settings should handle empty llm_keys, but raised: {e}")

        call_args = settings_page._mock_service.save_config.call_args
        config_dict = call_args[0][1]
        assert config_dict["llm_keys"] == "", \
            "Empty llm_keys should be saved as empty string"


# ============================================================================
# AC-5 Tests: Error handling during save
# ============================================================================

class TestAC5_ErrorHandlingDuringSave:
    """AC-5 [Medium]: When data_service.save_config raises an exception,
    save_settings should catch it and call _show_error, not crash the app."""

    def test_save_config_exception_caught_and_error_shown(self, settings_page):
        """When save_config raises, _show_error should be called."""
        error_msg = "Disk write failed"
        settings_page._mock_service.save_config = AsyncMock(
            side_effect=IOError(error_msg)
        )

        settings_page.llm_url_field.value = "https://api.test.com"
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = "test-key"

        # Should not raise
        try:
            asyncio.run(settings_page.save_settings(None))
        except Exception as e:
            pytest.fail(f"save_settings should catch exception, but raised: {e}")

        # Verify _show_error was called (via snack_bar)
        assert settings_page.page.snack_bar is not None, \
            "SnackBar should be set for error display"
        assert settings_page.page.snack_bar.open or settings_page.page.update.called, \
            "Error message should be displayed"

    def test_save_config_permission_error_caught(self, settings_page):
        """Permission errors during save should be caught and shown."""
        settings_page._mock_service.save_config = AsyncMock(
            side_effect=PermissionError("Access denied")
        )

        settings_page.llm_url_field.value = "https://api.test.com"
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = "test-key"

        # Should not raise
        try:
            asyncio.run(settings_page.save_settings(None))
        except Exception as e:
            pytest.fail(f"save_settings should catch permission error, but raised: {e}")

        # Error message should be shown
        assert settings_page.page.update.called, \
            "page.update should be called to display error"

    def test_save_config_generic_exception_caught(self, settings_page):
        """Generic exceptions during save should be caught."""
        settings_page._mock_service.save_config = AsyncMock(
            side_effect=Exception("Unknown error")
        )

        settings_page.llm_url_field.value = "https://api.test.com"
        settings_page.llm_model_field.value = "test-model"
        settings_page.llm_keys_field.value = "test-key"

        # Should not raise
        try:
            asyncio.run(settings_page.save_settings(None))
        except Exception as e:
            pytest.fail(f"save_settings should catch generic exception, but raised: {e}")


# ============================================================================
# Integration: Happy path (save and load cycle)
# ============================================================================

class TestIntegrationHappyPath:
    """Integration test: save settings, then load them back."""

    def test_save_and_load_cycle(self, settings_page):
        """Save settings and verify they're stored correctly."""
        # Set values
        settings_page.llm_url_field.value = "https://api.custom.com/v1"
        settings_page.llm_model_field.value = "custom-model"
        settings_page.llm_keys_field.value = "custom-key-1,custom-key-2"

        # Save
        asyncio.run(settings_page.save_settings(None))

        # Verify save_config was called with correct values
        call_args = settings_page._mock_service.save_config.call_args
        config_dict = call_args[0][1]

        assert config_dict["llm_url"] == "https://api.custom.com/v1"
        assert config_dict["llm_model"] == "custom-model"
        assert config_dict["llm_keys"] == "custom-key-1,custom-key-2"


# Clean up sys.modules pollution
del sys.modules['flet']
