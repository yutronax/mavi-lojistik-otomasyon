#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for admin-panel-ayarlar-temizlik-tasarim (AC-1, AC-3, AC-4, AC-S1, regressions).

Acceptance Criteria (from atdd.md):
1. [Critical] AC-1: GET /api/settings çağrıldığında yanıttaki `editable` listesi ve
   `settings` sözlüğü START_HOUR/END_HOUR İÇERMEMELİ — sadece kalan 10 anahtar dönmeli.
2. [Critical] AC-2: Frontend loadSet() dinamik render, editable listesinden START_HOUR/END_HOUR
   otomatik düşer (hiçbir <label>/<input> üretilmez).
3. [High] AC-3: POST /api/settings geçerli ayar (FETCH_HOURS_BACK) güncellenince
   200 + {ok:true} dönmeli, .env dosyasına yazılmalı.
4. [High] AC-4: .env dosyasında eski START_HOUR/END_HOUR satırları varken,
   GET/POST /api/settings çalışıp bu satırlara dokunulmaz.
5. [High] AC-S1 (threat-model): POST /api/settings'e START_HOUR gönderildiğinde
   (artık allowlist'te yok), .env'e YAZILMAMALI (satır oluşmaz/değişmez).
6. Regresyon: boş updates → 400 + {"error": "Güncellenecek ayar yok"}
7. Regresyon: token yok → 401 + {"error": "Yetkisiz"}

Test Stratejisi:
- Unit: settings_get/settings_save Flask route'ları, EDITABLE_ENV_KEYS filtreleme
- Integration: GET sonrası POST döngüsü, .env dosyasına yazma doğrulaması
- AC-S1: stale/eski anahtar gönderip allowlist dışı olduğunu doğrulama
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
    # Burada START_HOUR/END_HOUR olması gerekiyor, AC-4 test etmek için
    initial_content = """\
FETCH_HOURS_BACK=48
DUPLICATE_CHECK_HOURS=24
DEFAULT_UI_FILTER_MINUTES=60
WHATSAPP_POLL_INTERVAL=10
START_HOUR=08
END_HOUR=20
AUTO_SUBMIT=true
BATCH_SLEEP_TIME=5
LOOP_WAIT_TIME=30
DEEPSEEK_API_KEY=test_key_1
GROQ_API_KEY=test_key_2
GEMINI_API_KEY=test_key_3
"""
    temp_env.write_text(initial_content, encoding='utf-8')

    # Monkeypatch: admin_panel.ENV_PATH'i geçici dosyaya yönlendir
    with patch.object(admin_panel, 'ENV_PATH', str(temp_env)):
        yield temp_env


class TestSettingsGetCleanup:
    """
    AC-1 & AC-2: GET /api/settings çağrıldığında START_HOUR/END_HOUR
    içermemeli, sadece 10 anahtar dönmeli.
    """

    def test_get_settings_excludes_start_end_hour(self, client, valid_token, temp_env_file):
        """
        AC-1: GET /api/settings çağrıldığında yanıttaki `editable` listesi ve
        `settings` sözlüğü START_HOUR/END_HOUR içermez — sadece 10 anahtar dönmeli.

        Şu an: 12 anahtar dönüyor (START_HOUR + END_HOUR + 10 diğer)
        Code-copilot uygulandıktan sonra: 10 anahtar dönmeli
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = client.get("/api/settings", headers=headers)

        assert response.status_code == 200
        data = response.get_json()

        # Kontrol: editable listesi START_HOUR/END_HOUR içermemeli
        editable = data.get("editable", [])
        assert "START_HOUR" not in editable, "editable listesi START_HOUR içeriyor (AC-1 ihlali)"
        assert "END_HOUR" not in editable, "editable listesi END_HOUR içeriyor (AC-1 ihlali)"

        # Beklenen 11 anahtar
        expected_keys = {
            "FETCH_HOURS_BACK", "DUPLICATE_CHECK_HOURS", "DEFAULT_UI_FILTER_MINUTES",
            "WHATSAPP_POLL_INTERVAL", "AUTO_SUBMIT", "BATCH_SLEEP_TIME",
            "LOOP_WAIT_TIME", "DEEPSEEK_API_KEY", "GROQ_API_KEY", "GEMINI_API_KEY",
            "AI_HOURLY_SPEND_CAP_TRY"
        }
        actual_keys = set(editable)
        assert actual_keys == expected_keys, (
            f"editable anahtarları eşleşmiyor. "
            f"Beklenen: {expected_keys}, Alınan: {actual_keys}"
        )

        # settings sözlüğü de START_HOUR/END_HOUR içermemeli
        settings = data.get("settings", {})
        assert "START_HOUR" not in settings, "settings START_HOUR içeriyor (AC-1 ihlali)"
        assert "END_HOUR" not in settings, "settings END_HOUR içeriyor (AC-1 ihlali)"

    def test_editable_count_is_eleven(self, client, valid_token, temp_env_file):
        """
        Kontrol: editable listesinin uzunluğu tam olarak 11 mi?
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        response = client.get("/api/settings", headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        editable = data.get("editable", [])

        assert len(editable) == 11, (
            f"editable listesinin uzunluğu 11 olmalı, ama {len(editable)} (AC-1 ihlali)"
        )


class TestSettingsSave:
    """
    AC-3: POST /api/settings geçerli ayar güncellenince 200 + {ok:true} dönmeli,
    .env dosyasına yazılmalı.
    """

    def test_post_settings_save_valid_key(self, client, valid_token, temp_env_file):
        """
        AC-3: POST /api/settings FETCH_HOURS_BACK=72 gönder, 200 + {ok:true} al,
        .env dosyasında FETCH_HOURS_BACK=72 yazılı mı?
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        body = {"settings": {"FETCH_HOURS_BACK": "72"}}

        response = client.post("/api/settings", json=body, headers=headers)

        assert response.status_code == 200
        data = response.get_json()
        assert data.get("ok") is True, f"Yanıtta ok:true beklendi, alınan: {data}"

        # .env dosyasında yazılı mı kontrol et
        env_content = temp_env_file.read_text(encoding='utf-8')
        assert "FETCH_HOURS_BACK=72" in env_content, (
            f".env dosyasında FETCH_HOURS_BACK=72 bulunamadı. "
            f"Dosya içeriği:\n{env_content}"
        )

    def test_post_settings_multiple_keys(self, client, valid_token, temp_env_file):
        """
        AC-3: Birden fazla geçerli anahtar güncellenebiliyor mu?
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


class TestOldEnvLinesPreserved:
    """
    AC-4: .env dosyasında eski START_HOUR/END_HOUR satırları varken,
    GET/POST /api/settings çalışıp bu satırlara dokunulmaz.
    """

    def test_get_settings_ignores_start_hour_line(self, client, valid_token, temp_env_file):
        """
        AC-4: .env'de START_HOUR=08 satırı varken, GET /api/settings çağrıldıktan
        sonra .env dosyasında START_HOUR satırı hâlâ orada mı?
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Başlangıç: .env'de START_HOUR=08 var
        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "START_HOUR=08" in env_content_before, ".env'de START_HOUR başlangıçta yok"

        # GET çağrı
        response = client.get("/api/settings", headers=headers)
        assert response.status_code == 200

        # Sonra: .env'de START_HOUR=08 hâlâ var mı (dokunulmuş mı)?
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "START_HOUR=08" in env_content_after, (
            "GET /api/settings sonrası .env'de START_HOUR satırı silinmiş/değişmiş (AC-4 ihlali)"
        )

    def test_post_settings_preserves_old_lines(self, client, valid_token, temp_env_file):
        """
        AC-4: POST /api/settings FETCH_HOURS_BACK güncellenirken,
        eski START_HOUR/END_HOUR satırları dokunulmaz.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Başlangıç: .env'de START_HOUR ve END_HOUR var
        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "START_HOUR=08" in env_content_before
        assert "END_HOUR=20" in env_content_before

        # POST: FETCH_HOURS_BACK güncellensin
        body = {"settings": {"FETCH_HOURS_BACK": "120"}}
        response = client.post("/api/settings", json=body, headers=headers)
        assert response.status_code == 200

        # Sonra: START_HOUR/END_HOUR hâlâ orada mı?
        env_content_after = temp_env_file.read_text(encoding='utf-8')
        assert "START_HOUR=08" in env_content_after, (
            "POST sonrası .env'de START_HOUR satırı değişmiş/silinmiş (AC-4 ihlali)"
        )
        assert "END_HOUR=20" in env_content_after, (
            "POST sonrası .env'de END_HOUR satırı değişmiş/silinmiş (AC-4 ihlali)"
        )
        assert "FETCH_HOURS_BACK=120" in env_content_after, (
            "POST sonrası FETCH_HOURS_BACK güncellenememiş"
        )


class TestAllowlistEnforcement:
    """
    AC-S1 (threat-model): Eski/stale istemci START_HOUR gönderirse,
    .env'e YAZILMAMALI (allowlist dışı).
    """

    def test_disallowed_key_not_written_to_env(self, client, valid_token, temp_env_file):
        """
        AC-S1: POST /api/settings {"settings": {"START_HOUR": "99", "FETCH_HOURS_BACK": "5"}}
        gönder. START_HOUR artık EDITABLE_ENV_KEYS'te yok, bu yüzden .env'e yazılmaz.
        FETCH_HOURS_BACK ise normal şekilde yazılır.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Başlangıç: .env'de START_HOUR=08 var
        env_content_before = temp_env_file.read_text(encoding='utf-8')
        assert "START_HOUR=08" in env_content_before

        # POST: START_HOUR (allowlist dışı) + FETCH_HOURS_BACK (geçerli) gönder
        body = {
            "settings": {
                "START_HOUR": "99",        # Allowlist dışı (threat)
                "FETCH_HOURS_BACK": "5"    # Geçerli
            }
        }
        response = client.post("/api/settings", json=body, headers=headers)

        # 200 + ok:true dönmeli (diğer geçerli anahtarlar varsa)
        assert response.status_code == 200
        data = response.get_json()
        assert data.get("ok") is True

        # .env dosyasında:
        # 1. START_HOUR satırı değişmemeli (eski değer korunmalı)
        # 2. FETCH_HOURS_BACK=5 yazılmış olmalı
        env_content_after = temp_env_file.read_text(encoding='utf-8')

        assert "START_HOUR=08" in env_content_after, (
            "AC-S1 ihlali: START_HOUR (allowlist dışı) .env'e yazılmış veya değiştirilmiş"
        )
        assert "FETCH_HOURS_BACK=5" in env_content_after, (
            "FETCH_HOURS_BACK güncellemesi başarısız"
        )

        # START_HOUR=99 hiçbir yerde yazılı mı? (YAZILMAMALI)
        assert "START_HOUR=99" not in env_content_after, (
            "AC-S1 ihlali: START_HOUR=99 (allowlist dışı) .env'e yazıldı"
        )

    def test_only_disallowed_keys_returns_400(self, client, valid_token, temp_env_file):
        """
        AC-S1: Eğer gönderilen tüm anahtarlar allowlist dışı ise
        (boş updates), 400 + error dönmeli.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}

        # Yalnızca allowlist dışı anahtarlar gönder
        body = {"settings": {"START_HOUR": "99", "END_HOUR": "21"}}

        response = client.post("/api/settings", json=body, headers=headers)

        # 400 + error dönmeli (hiçbir geçerli anahtar yok)
        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data, "400'de error alanı beklendi"
        assert "Güncellenecek ayar yok" in data.get("error", ""), (
            f"Hata mesajı beklendi, alınan: {data.get('error', '')}"
        )


class TestRegressions:
    """
    Mevcut davranış (değişmeyen): boş updates, token yok, .env hata.
    """

    def test_empty_updates_returns_400(self, client, valid_token, temp_env_file):
        """
        Regresyon: body'de {"settings": {}} (boş) gönderilirse 400 + error dönmeli.
        """
        headers = {"Authorization": f"Bearer {valid_token}"}
        body = {"settings": {}}

        response = client.post("/api/settings", json=body, headers=headers)

        assert response.status_code == 400
        data = response.get_json()
        assert "error" in data
        assert "Güncellenecek ayar yok" in data.get("error", "")

    def test_no_auth_token_returns_401(self, client, temp_env_file):
        """
        Regresyon: Authorization header yok/geçersiz ise 401 + error dönmeli.
        """
        # Token yok
        response = client.get("/api/settings")
        assert response.status_code == 401
        data = response.get_json()
        assert data.get("error") == "Yetkisiz"

        # POST da aynı şekilde
        response = client.post("/api/settings", json={"settings": {"FETCH_HOURS_BACK": "50"}})
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

    def test_expired_token_returns_401(self, temp_env_file):
        """
        Regresyon: Süresi dolmuş token 401 dönmeli.
        """
        # Süresi dolmuş token oluştur
        expired_token = "expired_token_" + os.urandom(16).hex()
        admin_panel.TOKENS[expired_token] = time.time() - 10  # 10 saniye önce sona ermiş

        admin_panel.app.config['TESTING'] = True
        with admin_panel.app.test_client() as client:
            headers = {"Authorization": f"Bearer {expired_token}"}
            response = client.get("/api/settings", headers=headers)

            assert response.status_code == 401
            data = response.get_json()
            assert data.get("error") == "Yetkisiz"

        # Cleanup
        admin_panel.TOKENS.pop(expired_token, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
