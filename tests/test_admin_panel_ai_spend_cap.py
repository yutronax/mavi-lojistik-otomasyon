#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for ai-hourly-spend-cap-ayarlar-panelinde (AC-1, AC-2, AC-S1, AC-5, regressions).

Acceptance Criteria (from atdd.md):
1. [Critical] AC-1: GET /api/settings çağrıldığında yanıttaki `editable` listesi
   `AI_HOURLY_SPEND_CAP_TRY`'ı içerir.
2. [Critical] AC-2: POST /api/settings ile {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "15"}}
   gönderilince 200 + {ok:true} dönmeli, .env dosyasına AI_HOURLY_SPEND_CAP_TRY=15 yazılmalı.
3. [Critical] AC-S1 (threat-model): POST /api/settings ile geçersiz değer (abc, "", -5)
   gönderilirse 400 ile reddedilir, .env'e YAZILMAZ. Geçerli sıfır ("0") için ise 200 beklenmeli.
4. [Medium] AC-5: Diğer EDITABLE_ENV_KEYS (örn. FETCH_HOURS_BACK) validasyonsuz kalmalı —
   POST /api/settings ile {"settings": {"FETCH_HOURS_BACK": "abc"}} gönderilince 200 dönmeli,
   "abc" .env'e yazılmalı.
5. [Critical] Davranış Sözleşmesi "Kısmi başarı": AI_HOURLY_SPEND_CAP_TRY geçersizken
   aynı istekte başka geçerli anahtar da varsa, TÜM istek 400 ile reddedilir.

Test Stratejisi:
- Unit: GET /api/settings yanıtının AI_HOURLY_SPEND_CAP_TRY içerip içermediği
- Integration: POST /api/settings ile geçerli/geçersiz değer gönderip .env doğrulaması
- AC-S1: Validasyon testleri (abc, "", -5, 0)
- AC-5: Regresyon — diğer anahtarlar validasyonsuz kalmalı
"""

import pytest
import os
import sys
import json
import time
import tempfile
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out heavy imports BEFORE importing admin_panel (sys.modules pollution koruması)
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

# Patch pyngrok
sys.modules['pyngrok'] = MagicMock()
sys.modules['pyngrok.conf'] = MagicMock()

# Patch config and reporter modules
_reporter_mock = MagicMock()
_reporter_mock.Reporter = MagicMock()
sys.modules['src.utils.reporter'] = _reporter_mock

_config_mock = MagicMock()
_config_mock.DEFAULT_CONFIG = {}
_config_mock.WHAPI_TIMEOUT = 30
sys.modules['src.utils.config'] = _config_mock

# Patch OrchestratorSDK
_veri_cekici_mock = MagicMock()
_veri_cekici_mock.OrchestratorSDK = MagicMock()
sys.modules['src.parsers.veri_cekici_ayristirici'] = _veri_cekici_mock

# Import admin_panel (which uses Flask)
from src.api import admin_panel

# Clean up sys.modules pollution (3.PARTI olmayan modülleri temizle)
del sys.modules['src.parsers.veri_cekici_ayristirici']
del sys.modules['src.utils.reporter']
del sys.modules['src.utils.config']


@pytest.fixture
def client():
    """Flask test_client fixture — admin_panel uygulaması üzerinde test çalıştırır."""
    admin_panel.app.config['TESTING'] = True
    with admin_panel.app.test_client() as c:
        yield c


@pytest.fixture
def valid_token():
    """Geçerli bir auth token oluştur ve TOKENS sözlüğüne ekle."""
    token = "test_token_" + os.urandom(16).hex()
    admin_panel.TOKENS[token] = time.time() + 3600  # 1 saat geçerli
    yield token
    # Cleanup: token'ı sözlükten çıkar
    admin_panel.TOKENS.pop(token, None)


@pytest.fixture
def temp_env_file(tmp_path):
    """Test için geçici .env dosyası oluştur ve ENV_PATH'i oraya yönlendir."""
    temp_env = tmp_path / ".env.test"
    # Test .env dosyasına başlangıç ayarları yaz
    # AI_HOURLY_SPEND_CAP_TRY başlangıçta "9" (varsayılan)
    initial_content = """\
FETCH_HOURS_BACK=48
DUPLICATE_CHECK_HOURS=24
DEFAULT_UI_FILTER_MINUTES=60
WHATSAPP_POLL_INTERVAL=10
AUTO_SUBMIT=true
BATCH_SLEEP_TIME=5
LOOP_WAIT_TIME=30
DEEPSEEK_API_KEY=test_key_1
GROQ_API_KEY=test_key_2
GEMINI_API_KEY=test_key_3
AI_HOURLY_SPEND_CAP_TRY=9
"""
    temp_env.write_text(initial_content, encoding='utf-8')

    # Monkeypatch: admin_panel.ENV_PATH'i geçici dosyaya yönlendir
    with patch.object(admin_panel, 'ENV_PATH', str(temp_env)):
        yield temp_env


class TestSettingsGetAiSpendCap:
    """
    AC-1: GET /api/settings çağrıldığında yanıttaki `editable` listesi
    `AI_HOURLY_SPEND_CAP_TRY`'ı içermelidir.
    """

    def test_get_settings_includes_ai_hourly_spend_cap(self, client, valid_token, temp_env_file):
        """
        AC-1: GET /api/settings çağrıldığında yanıttaki `editable` listesi
        `AI_HOURLY_SPEND_CAP_TRY`'ı içerir.

        Note: Bu test şu an BAŞARISIZ olacak (red) — code-copilot tarafından
        EDITABLE_ENV_KEYS'e "AI_HOURLY_SPEND_CAP_TRY" ekleninceye kadar.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = client.get("/api/settings", headers=headers)

        assert response.status_code == 200
        data = response.get_json()

        # Kontrol: editable listesi AI_HOURLY_SPEND_CAP_TRY içermeli
        editable = data.get("editable", [])
        assert "AI_HOURLY_SPEND_CAP_TRY" in editable, (
            f"editable listesi AI_HOURLY_SPEND_CAP_TRY içermiyor. "
            f"Editable: {editable}"
        )

        # Settings sözlüğü de AI_HOURLY_SPEND_CAP_TRY'ı içermeli
        settings = data.get("settings", {})
        assert "AI_HOURLY_SPEND_CAP_TRY" in settings, (
            f"settings sözlüğü AI_HOURLY_SPEND_CAP_TRY içermiyor. "
            f"Settings: {settings}"
        )

        # Mevcut değer başlangıçta "9" olmalı
        assert settings.get("AI_HOURLY_SPEND_CAP_TRY") == "9", (
            f"Başlangıç değeri '9' beklendi, alınan: {settings.get('AI_HOURLY_SPEND_CAP_TRY')}"
        )


class TestSettingsSaveAiSpendCap:
    """
    AC-2: POST /api/settings ile geçerli sayısal değer gönderilince
    200 + {ok:true} dönmeli, .env dosyasına yazılmalı.
    """

    def test_post_settings_save_valid_ai_spend_cap(self, client, valid_token, temp_env_file):
        """
        AC-2: POST /api/settings {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "15"}}
        gönder, 200 + {ok:true} al, .env dosyasında AI_HOURLY_SPEND_CAP_TRY=15 yazılı mı?

        Note: Bu test şu an BAŞARISIZ olacak (red) — code-copilot tarafından
        EDITABLE_ENV_KEYS'e "AI_HOURLY_SPEND_CAP_TRY" ve validasyon ekleninceye kadar.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "15"}}

        response = client.post("/api/settings", json=body, headers=headers)

        assert response.status_code == 200, (
            f"Durum kodu 200 beklendi, alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )
        data = response.get_json()
        assert data.get("ok") is True, f"Yanıtta ok:true beklendi, alınan: {data}"

        # .env dosyasında yazılı mı kontrol et
        env_content = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=15" in env_content, (
            f".env dosyasında AI_HOURLY_SPEND_CAP_TRY=15 bulunamadı. "
            f"Dosya içeriği:\n{env_content}"
        )

    def test_post_settings_save_valid_zero(self, client, valid_token, temp_env_file):
        """
        AC-2 edge case: POST /api/settings ile {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "0"}}
        gönderilince — sıfır GEÇERLİ (negatif değil, limit olarak anlamlı) — 200 dönmeli.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "0"}}

        response = client.post("/api/settings", json=body, headers=headers)

        assert response.status_code == 200, (
            f"Durum kodu 200 beklendi (sıfır geçerli), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )
        data = response.get_json()
        assert data.get("ok") is True

        # .env dosyasında yazılı mı kontrol et
        env_content = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=0" in env_content, (
            f".env dosyasında AI_HOURLY_SPEND_CAP_TRY=0 bulunamadı. "
            f"Dosya içeriği:\n{env_content}"
        )

    def test_post_settings_save_valid_float(self, client, valid_token, temp_env_file):
        """
        AC-2 edge case: POST /api/settings ile {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "9.5"}}
        gönderilince — ondalıklı sayı GEÇERLİ — 200 dönmeli.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "9.5"}}

        response = client.post("/api/settings", json=body, headers=headers)

        assert response.status_code == 200, (
            f"Durum kodu 200 beklendi (ondalıklı sayı geçerli), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )
        data = response.get_json()
        assert data.get("ok") is True

        # .env dosyasında yazılı mı kontrol et
        env_content = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9.5" in env_content


class TestValidationAiSpendCap:
    """
    AC-S1 (threat-model): POST /api/settings ile geçersiz değer gönderilirse
    400 ile reddedilir, .env'e YAZILMAZ.
    """

    def test_post_settings_invalid_string(self, client, valid_token, temp_env_file):
        """
        AC-S1: POST /api/settings {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "abc"}}
        gönder — geçersiz (sayı değil) — 400 dönmeli, .env'e yazılmaz.

        Note: Bu test şu an BAŞARISIZ olacak (red) — code-copilot tarafından
        validasyon ekleninceye kadar.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Başlangıç: .env'de AI_HOURLY_SPEND_CAP_TRY=9
        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_before

        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "abc"}}
        response = client.post("/api/settings", json=body, headers=headers)

        # 400 + error dönmeli
        assert response.status_code == 400, (
            f"Durum kodu 400 beklendi (geçersiz string), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )
        data = response.get_json()
        assert "error" in data, f"400'de error alanı beklendi, alınan: {data}"

        # .env dosyasında DEĞİŞİKLİK OLMAMALI — başlangıç değeri korunmalı
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_after, (
            f".env dosyasında AI_HOURLY_SPEND_CAP_TRY=9 değeri değişmiş/silinmiş. "
            f"Dosya içeriği:\n{env_content_after}"
        )
        assert "AI_HOURLY_SPEND_CAP_TRY=abc" not in env_content_after, (
            "AC-S1 ihlali: Geçersiz değer 'abc' .env'e yazıldı"
        )

    def test_post_settings_invalid_empty(self, client, valid_token, temp_env_file):
        """
        AC-S1: POST /api/settings {"settings": {"AI_HOURLY_SPEND_CAP_TRY": ""}}
        gönder — geçersiz (boş string) — 400 dönmeli, .env'e yazılmaz.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_before

        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": ""}}
        response = client.post("/api/settings", json=body, headers=headers)

        # 400 + error dönmeli
        assert response.status_code == 400, (
            f"Durum kodu 400 beklendi (boş string), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )

        # .env dosyasında DEĞİŞİKLİK OLMAMALI
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_after, (
            "Boş string sonrası .env dosyasında AI_HOURLY_SPEND_CAP_TRY=9 başlangıç değeri değişmiş"
        )

    def test_post_settings_invalid_negative(self, client, valid_token, temp_env_file):
        """
        AC-S1: POST /api/settings {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "-5"}}
        gönder — geçersiz (negatif sayı) — 400 dönmeli, .env'e yazılmaz.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_before

        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "-5"}}
        response = client.post("/api/settings", json=body, headers=headers)

        # 400 + error dönmeli
        assert response.status_code == 400, (
            f"Durum kodu 400 beklendi (negatif sayı), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )

        # .env dosyasında DEĞİŞİKLİK OLMAMALI
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_after, (
            "Negatif sayı sonrası .env dosyasında AI_HOURLY_SPEND_CAP_TRY=9 başlangıç değeri değişmiş"
        )
        assert "AI_HOURLY_SPEND_CAP_TRY=-5" not in env_content_after, (
            "AC-S1 ihlali: Negatif değer '-5' .env'e yazıldı"
        )

    def test_post_settings_invalid_inf(self, client, valid_token, temp_env_file):
        """
        AC-S1 (red-team): POST /api/settings {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "inf"}}
        gönder — geçersiz (infinity) — 400 dönmeli, .env'e yazılmaz.

        Red Team Bulgusu: Python'da float("inf") geçerli bir float'tır ve `< 0`
        karşılaştırmasını GEÇER (False döner). Limit sessizce devre dışı kalabilir.
        Çözüm: math.isfinite(value) kontrolü.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_before

        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "inf"}}
        response = client.post("/api/settings", json=body, headers=headers)

        # 400 + error dönmeli
        assert response.status_code == 400, (
            f"Durum kodu 400 beklendi (infinity), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )

        # .env dosyasında DEĞİŞİKLİK OLMAMALI
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_after, (
            "Infinity sonrası .env dosyasında AI_HOURLY_SPEND_CAP_TRY=9 başlangıç değeri değişmiş"
        )
        assert "AI_HOURLY_SPEND_CAP_TRY=inf" not in env_content_after, (
            "AC-S1 ihlali: Infinity değeri 'inf' .env'e yazıldı"
        )

    def test_post_settings_invalid_nan(self, client, valid_token, temp_env_file):
        """
        AC-S1 (red-team): POST /api/settings {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "nan"}}
        gönder — geçersiz (NaN) — 400 dönmeli, .env'e yazılmaz.

        Red Team Bulgusu: Python'da float("nan") geçerli bir float'tır ve `< 0`
        karşılaştırmasını her zaman False dönerek geçer. Limit sessizce devre dışı kalabilir.
        Çözüm: math.isfinite(value) kontrolü.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_before

        body = {"settings": {"AI_HOURLY_SPEND_CAP_TRY": "nan"}}
        response = client.post("/api/settings", json=body, headers=headers)

        # 400 + error dönmeli
        assert response.status_code == 400, (
            f"Durum kodu 400 beklendi (NaN), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )

        # .env dosyasında DEĞİŞİKLİK OLMAMALI
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_after, (
            "NaN sonrası .env dosyasında AI_HOURLY_SPEND_CAP_TRY=9 başlangıç değeri değişmiş"
        )
        assert "AI_HOURLY_SPEND_CAP_TRY=nan" not in env_content_after, (
            "AC-S1 ihlali: NaN değeri 'nan' .env'e yazıldı"
        )


class TestPartialFailureAiSpendCap:
    """
    Davranış Sözleşmesi "Kısmi başarı": AI_HOURLY_SPEND_CAP_TRY geçersizken
    aynı istekte başka geçerli anahtar da varsa, TÜM istek 400 ile reddedilir.
    """

    def test_post_settings_partial_failure_ai_cap_invalid_other_valid(
        self, client, valid_token, temp_env_file
    ):
        """
        Davranış: AI_HOURLY_SPEND_CAP_TRY=abc (geçersiz) + FETCH_HOURS_BACK=10 (geçerli)
        gönderilirse, TÜM istek 400 ile reddedilir — FETCH_HOURS_BACK bile .env'e yazılmaz.

        Note: Bu test şu an BAŞARISIZ olacak (red) — code-copilot tarafından
        validasyon ekleninceye kadar.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Başlangıç değerlerini kaydet
        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "FETCH_HOURS_BACK=48" in env_content_before
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_before

        # Geçersiz + geçerli anahtarlar gönder
        body = {
            "settings": {
                "AI_HOURLY_SPEND_CAP_TRY": "abc",  # Geçersiz
                "FETCH_HOURS_BACK": "10"  # Geçerli
            }
        }
        response = client.post("/api/settings", json=body, headers=headers)

        # 400 + error dönmeli (geçersiz anahtar yüzünden TÜM istek reddedilir)
        assert response.status_code == 400, (
            f"Durum kodu 400 beklendi (kısmi başarı → TÜM reddedilmeli), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )

        # .env dosyasında YAKIN BİR DEĞİŞİKLİK DE OLMAMALI
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "FETCH_HOURS_BACK=48" in env_content_after, (
            "Kısmi başarı → TÜM reddedilmeli: FETCH_HOURS_BACK=10 .env'e yazıldı (HATA)"
        )
        assert "FETCH_HOURS_BACK=10" not in env_content_after, (
            "Kısmi başarı → TÜM reddedilmeli: FETCH_HOURS_BACK güncellenemesi gerekiyordu ama reddedildi"
        )
        assert "AI_HOURLY_SPEND_CAP_TRY=9" in env_content_after, (
            "Kısmi başarı sonrası .env'de AI_HOURLY_SPEND_CAP_TRY=9 başlangıç değeri değişmiş"
        )


class TestRegressionAiSpendCap:
    """
    AC-5 & Regresyon: Diğer EDITABLE_ENV_KEYS validasyonsuz kalmalı.
    """

    def test_post_settings_other_keys_unvalidated(self, client, valid_token, temp_env_file):
        """
        AC-5: POST /api/settings {"settings": {"FETCH_HOURS_BACK": "abc"}}
        gönderilince — bu anahtar için validasyon YOK — 200 dönmeli, "abc" .env'e yazılmalı.

        Bu, mevcut davranışın DEĞİŞMEDİĞİ kontrol eden regresyon testidir.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        body = {"settings": {"FETCH_HOURS_BACK": "abc"}}

        response = client.post("/api/settings", json=body, headers=headers)

        # 200 + ok:true dönmeli (geçersiz değer de giriş olarak kabul edilir — validasyon YOK)
        assert response.status_code == 200, (
            f"Durum kodu 200 beklendi (FETCH_HOURS_BACK validasyonsuz), alınan: {response.status_code}. "
            f"Yanıt: {response.get_json()}"
        )
        data = response.get_json()
        assert data.get("ok") is True

        # .env dosyasında "abc" yazılı mı kontrol et (mevcut davranış)
        env_content = temp_env_file.read_text(encoding='utf-8')
        assert "FETCH_HOURS_BACK=abc" in env_content, (
            f".env dosyasında FETCH_HOURS_BACK=abc bulunamadı (regresyon: validasyonsuz davranış değişmiş). "
            f"Dosya içeriği:\n{env_content}"
        )

    def test_post_settings_multiple_valid_keys(self, client, valid_token, temp_env_file):
        """
        Regresyon: Birden fazla geçerli anahtar güncellenebiliyor mu? (AC-2 desteği)
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        body = {
            "settings": {
                "FETCH_HOURS_BACK": "96",
                "BATCH_SLEEP_TIME": "10",
                "DUPLICATE_CHECK_HOURS": "30"
            }
        }

        response = client.post("/api/settings", json=body, headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("ok") is True

        # .env dosyasında tüm değerler yazılı mı?
        env_content = temp_env_file.read_text(encoding='utf-8')
        assert "FETCH_HOURS_BACK=96" in env_content
        assert "BATCH_SLEEP_TIME=10" in env_content
        assert "DUPLICATE_CHECK_HOURS=30" in env_content

    def test_get_settings_has_ai_hourly_spend_cap_or_not(self, client, valid_token, temp_env_file):
        """
        Regresyon: GET /api/settings çağrıldığında editable listesinin
        beklenen anahtarları içerdiğini doğrula.

        Not: AI_HOURLY_SPEND_CAP_TRY'ın listede olup olmadığı,
        code-copilot uygulamasına bağlı. Bu test şu an başarısız olabilir (red).
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = client.get("/api/settings", headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        editable = data.get("editable", [])

        # En az 10 temel anahtar var olmalı (AI_HOURLY_SPEND_CAP_TRY eklendikten sonra 11 olacak)
        assert len(editable) >= 10, (
            f"editable listesi en az 10 anahtar içermeli, alınan {len(editable)}: {editable}"
        )

        # Temel anahtarlar hâlâ orada mı?
        expected_base = {
            "FETCH_HOURS_BACK", "DUPLICATE_CHECK_HOURS", "DEFAULT_UI_FILTER_MINUTES",
            "WHATSAPP_POLL_INTERVAL", "AUTO_SUBMIT", "BATCH_SLEEP_TIME",
            "LOOP_WAIT_TIME", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY"
        }
        actual = set(editable)
        assert expected_base.issubset(actual), (
            f"Temel anahtarlardan bazıları eksik. "
            f"Beklenen: {expected_base}, Alınan: {actual}"
        )


class TestAuthenticationAiSpendCap:
    """
    Regresyon: Auth kontrolleri çalışıyor mu? (AC-S1 beraberinde test)
    """

    def test_no_auth_token_returns_401(self, client, temp_env_file):
        """
        Regresyon: Authorization header yok/geçersiz ise GET 401 dönmeli.
        """
        response = client.get("/api/settings")
        assert response.status_code == 401
        data = response.get_json()
        assert data.get("error") == "Yetkisiz"

        # POST da aynı şekilde
        response = client.post("/api/settings", json={"settings": {"AI_HOURLY_SPEND_CAP_TRY": "15"}})
        assert response.status_code == 401

    def test_invalid_token_returns_401(self, client, temp_env_file):
        """
        Regresyon: Geçersiz token ile 401 dönmeli.
        """
        headers = {"Authorization": "Bearer invalid_token_xyz"}
        response = client.get("/api/settings", headers=headers)

        assert response.status_code == 401
        data = response.get_json()
        assert data.get("error") == "Yetkisiz"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
