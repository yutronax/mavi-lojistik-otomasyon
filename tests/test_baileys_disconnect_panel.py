#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for /api/whatsapp/disconnect endpoint (panel-baileys-oturum-kapat).

Acceptance Criteria (atdd.md):
1. [Critical] Happy path (oturum var, silinir, pm2 restart başarılı) → 200 + {"ok": true, "status": "logged_out"}
2. [High] Zaten kopuk (auth_info_baileys/ klasörü yok, idempotent) → 200 + {"ok": true, "status": "already_logged_out"}
3. [High] Yetkisiz erişim (login yok) → 401 + {"error": "Yetkisiz"}
4. [High] Dosya silme başarısız (izin hatası) → 500 + {"ok": false, "error": "...", "step": "file_delete"}
5. [Medium] Kısmi başarı (dosya silindi ama pm2 restart başarısız) → 500 + {"ok": false, "error": "...", "step": "pm2_restart", "file_deleted": true}
6. [Medium] Buton confirm dialogu → FRONTEND ONLY, not tested in backend suite

Test Technique:
- require_auth ile korunan route test etme: test_client() + Authorization Bearer header
- TOKENS dict'ine token yazarak geçerli bir token simüle etme: admin_panel.TOKENS[token] = time.time() + 3600
- Dosya silme mock'lama: patch.object() ile shutil.rmtree veya admin_panel._pm2()
- PM2 çağrısını mock'lama: unittest.mock.patch.object(admin_panel, '_pm2', return_value=(success, output))
- Gerçek dosya silme senaryosu: tempfile.mkdtemp() ile geçici klasör oluşturup test etme

Important Notes (from plan.md):
- Response format uses `ok` (not `success`) — consistent with existing `/api/service/<action>` route
- BAILEYS_AUTH_DIR constant in admin_panel module: os.path.join(PROJECT_ROOT, "sidecar", "auth_info_baileys")
- PM2 restart call: _pm2(["restart", "mavi-baileys-bridge"])
- Authorization error message: "Yetkisiz" (from require_auth decorator)
"""

import pytest
import os
import sys
import time
import tempfile
import shutil
from unittest.mock import patch, MagicMock, call
from io import StringIO

# Add project root to path
sys.path.insert(0, os.getcwd())

from src.api import admin_panel


class TestDisconnectAuth:
    """AC-3: Yetkisiz erişim (login yok) → 401"""

    def test_disconnect_endpoint_401_without_token(self):
        """
        Given: /api/whatsapp/disconnect endpoint'ine login OLMADAN istek atılır
        When: Authorization header'ı yok
        Then: 401 Unauthorized + {"error": "Yetkisiz"} döner
        """
        response = admin_panel.app.test_client().post('/api/whatsapp/disconnect')
        assert response.status_code == 401, f"Expected 401, got {response.status_code}"
        data = response.get_json()
        assert data.get("error") == "Yetkisiz", f"Expected error 'Yetkisiz', got {data}"

    def test_disconnect_endpoint_401_with_invalid_token(self):
        """
        Given: /api/whatsapp/disconnect'e geçersiz Bearer token ile istek atılır
        When: Token TOKENS dict'inde yok
        Then: 401 döner
        """
        response = admin_panel.app.test_client().post(
            '/api/whatsapp/disconnect',
            headers={'Authorization': 'Bearer invalid_token_xyz'}
        )
        assert response.status_code == 401

    def test_disconnect_endpoint_401_with_expired_token(self):
        """
        Given: /api/whatsapp/disconnect'e geçerliyken süresi dolmuş Bearer token ile istek atılır
        When: Token TOKENS dict'inde ama expiry < time.time()
        Then: 401 döner
        """
        expired_token = 'expired_disconnect_token_' + str(time.time())
        admin_panel.TOKENS[expired_token] = time.time() - 3600

        try:
            response = admin_panel.app.test_client().post(
                '/api/whatsapp/disconnect',
                headers={'Authorization': f'Bearer {expired_token}'}
            )
            assert response.status_code == 401
        finally:
            if expired_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[expired_token]

    def test_disconnect_endpoint_401_with_malformed_bearer(self):
        """
        Given: Authorization header'ı "Bearer " ama token boş
        When: /api/whatsapp/disconnect'e istek atılır
        Then: 401 döner
        """
        response = admin_panel.app.test_client().post(
            '/api/whatsapp/disconnect',
            headers={'Authorization': 'Bearer'}
        )
        assert response.status_code == 401


class TestDisconnectHappyPath:
    """AC-1: Happy path (oturum var, silinir, pm2 restart başarılı) → 200 + {"ok": true, "status": "logged_out"}"""

    def test_disconnect_happy_path_with_real_directory(self):
        """
        Given: Geçerli token, BAILEYS_AUTH_DIR klasörü mevcut (dosyalar var)
        When: /api/whatsapp/disconnect'e POST isteği atılır
        Then: 200 OK + {"ok": true, "status": "logged_out"} döner
        Yan etki: auth_info_baileys/ silinir, pm2 restart çağrılır
        """
        valid_token = 'test_disconnect_happy_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        # Geçici bir auth klasörü oluştur
        temp_auth_dir = tempfile.mkdtemp(prefix='baileys_auth_')

        try:
            # Klasörün içine test dosyası koy
            test_file_path = os.path.join(temp_auth_dir, 'creds.json')
            with open(test_file_path, 'w') as f:
                f.write('{"test": "credential"}')

            # _pm2() fonksiyonunu mock'la (gerçek pm2 komutu çalıştırmasın)
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch.object(admin_panel, '_pm2', return_value=(True, "Restarted successfully")) as mock_pm2:
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    # Assertions
                    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                    data = response.get_json()
                    assert data.get("ok") is True, f"Expected ok: true, got {data.get('ok')}"
                    assert data.get("status") == "logged_out", f"Expected status 'logged_out', got {data.get('status')}"

                    # Dosya silindiğini doğrula
                    assert not os.path.exists(temp_auth_dir), f"Auth directory should be deleted, but still exists"

                    # pm2 restart çağrıldığını doğrula
                    mock_pm2.assert_called_once_with(["restart", "mavi-baileys-bridge"])

        finally:
            # Cleanup
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)

    def test_disconnect_happy_path_response_structure(self):
        """
        Given: Geçerli token, klasör mevcut, pm2 başarılı
        When: /api/whatsapp/disconnect çağrılır
        Then: response şu alanları içerir: ok, status
        """
        valid_token = 'test_disconnect_response_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp(prefix='baileys_auth_')

        try:
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch.object(admin_panel, '_pm2', return_value=(True, "OK")):
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    data = response.get_json()
                    assert "ok" in data, "Response must contain 'ok' field"
                    assert "status" in data, "Response must contain 'status' field"
                    assert isinstance(data["ok"], bool), "'ok' should be boolean"
                    assert isinstance(data["status"], str), "'status' should be string"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)


class TestDisconnectAlreadyDisconnected:
    """AC-2: Zaten kopuk (auth_info_baileys/ klasörü yok, idempotent) → 200 + {"ok": true, "status": "already_logged_out"}"""

    def test_disconnect_idempotent_directory_not_found(self):
        """
        Given: BAILEYS_AUTH_DIR klasörü yok (oturum zaten kopuk)
        When: /api/whatsapp/disconnect çağrılır
        Then: 200 OK + {"ok": true, "status": "already_logged_out"} döner
        Yan etki: pm2 restart yine denenir (idempotent)
        """
        valid_token = 'test_disconnect_idempotent_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        # Non-existent directory path
        nonexistent_dir = os.path.join(tempfile.gettempdir(), 'nonexistent_baileys_' + str(time.time()))

        try:
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', nonexistent_dir):
                with patch.object(admin_panel, '_pm2', return_value=(True, "Restarted")) as mock_pm2:
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    # Assertions
                    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
                    data = response.get_json()
                    assert data.get("ok") is True, f"Expected ok: true (idempotent), got {data.get('ok')}"
                    assert data.get("status") == "already_logged_out", f"Expected status 'already_logged_out', got {data.get('status')}"

                    # pm2 restart yine çağrılmalı (idempotent)
                    mock_pm2.assert_called_once_with(["restart", "mavi-baileys-bridge"])

        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]

    def test_disconnect_idempotent_error_message_not_shown(self):
        """
        Given: Klasör yok
        When: /api/whatsapp/disconnect çağrılır
        Then: ok: true döner (error alanı olmaması gerekir veya hata olarak gösterilmemeli)
        """
        valid_token = 'test_disconnect_no_error_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        nonexistent_dir = os.path.join(tempfile.gettempdir(), 'never_exists_' + str(time.time()))

        try:
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', nonexistent_dir):
                with patch.object(admin_panel, '_pm2', return_value=(True, "OK")):
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    data = response.get_json()
                    # ok:true için error alanı olmamalı
                    if data.get("ok"):
                        assert "error" not in data or data.get("error") is None, \
                            "When ok:true, 'error' field should not be present or None"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]


class TestDisconnectFileDeletionError:
    """AC-4: Dosya silme başarısız (izin hatası) → 500 + {"ok": false, "error": "...", "step": "file_delete"}"""

    def test_disconnect_file_deletion_permission_error(self):
        """
        Given: BAILEYS_AUTH_DIR klasörü var ama silinme izni yok (PermissionError)
        When: /api/whatsapp/disconnect çağrılır
        Then: 500 + {"ok": false, "error": "...", "step": "file_delete"} döner
        Yan etki: pm2 restart HİÇ çağrılmaz
        """
        valid_token = 'test_disconnect_perm_error_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp(prefix='baileys_auth_readonly_')

        try:
            with open(os.path.join(temp_auth_dir, 'test.json'), 'w') as f:
                f.write('{}')

            # shutil.rmtree() işlemini mock'la ve PermissionError at
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch('shutil.rmtree', side_effect=PermissionError("Permission denied")) as mock_rmtree:
                    with patch.object(admin_panel, '_pm2', return_value=(True, "OK")) as mock_pm2:
                        response = admin_panel.app.test_client().post(
                            '/api/whatsapp/disconnect',
                            headers={'Authorization': f'Bearer {valid_token}'}
                        )

                        # Assertions
                        assert response.status_code == 500, f"Expected 500, got {response.status_code}"
                        data = response.get_json()
                        assert data.get("ok") is False, f"Expected ok: false, got {data.get('ok')}"
                        assert data.get("step") == "file_delete", f"Expected step 'file_delete', got {data.get('step')}"
                        assert data.get("error") is not None, "Error message should be provided"

                        # pm2 restart HİÇ çağrılmamalı
                        mock_pm2.assert_not_called()

        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)

    def test_disconnect_file_deletion_os_error(self):
        """
        Given: BAILEYS_AUTH_DIR klasörü var ama silme sırasında OS hatası (örn. device busy)
        When: /api/whatsapp/disconnect çağrılır
        Then: 500 + {"ok": false, "error": "...", "step": "file_delete"} döner
        """
        valid_token = 'test_disconnect_os_error_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp(prefix='baileys_auth_oserror_')

        try:
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch('shutil.rmtree', side_effect=OSError("Device or resource busy")) as mock_rmtree:
                    with patch.object(admin_panel, '_pm2') as mock_pm2:
                        response = admin_panel.app.test_client().post(
                            '/api/whatsapp/disconnect',
                            headers={'Authorization': f'Bearer {valid_token}'}
                        )

                        assert response.status_code == 500
                        data = response.get_json()
                        assert data.get("ok") is False
                        assert data.get("step") == "file_delete"
                        mock_pm2.assert_not_called()

        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)

    def test_disconnect_file_deletion_contains_step_field(self):
        """
        Given: Dosya silme başarısız
        When: Response döndürülür
        Then: "step" alanı kesinlikle var ve "file_delete" değerine sahip
        """
        valid_token = 'test_disconnect_step_field_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp()

        try:
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch('shutil.rmtree', side_effect=PermissionError("Denied")):
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    data = response.get_json()
                    assert "step" in data, "Response must contain 'step' field when file_delete fails"
                    assert data["step"] == "file_delete", "step should be 'file_delete'"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)


class TestDisconnectPartialSuccess:
    """AC-5: Kısmi başarı (dosya silindi ama pm2 restart başarısız) → 500 + {"ok": false, "error": "...", "step": "pm2_restart", "file_deleted": true}"""

    def test_disconnect_partial_success_pm2_failure(self):
        """
        Given: BAILEYS_AUTH_DIR silinebilir, ama pm2 restart başarısız olur
        When: /api/whatsapp/disconnect çağrılır
        Then: 500 + {"ok": false, "error": "...", "step": "pm2_restart", "file_deleted": true} döner
        Yan etki: Klasör silinmiş durumda kalır (rollback yok)
        """
        valid_token = 'test_disconnect_partial_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp(prefix='baileys_auth_partial_')

        try:
            # Klasörün içine test dosyası koy
            with open(os.path.join(temp_auth_dir, 'creds.json'), 'w') as f:
                f.write('{}')

            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                # pm2 restart başarısız olacak şekilde mock'la
                with patch.object(admin_panel, '_pm2', return_value=(False, "Service not found in PM2")) as mock_pm2:
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    # Assertions
                    assert response.status_code == 500, f"Expected 500, got {response.status_code}"
                    data = response.get_json()
                    assert data.get("ok") is False, f"Expected ok: false, got {data.get('ok')}"
                    assert data.get("step") == "pm2_restart", f"Expected step 'pm2_restart', got {data.get('step')}"
                    assert data.get("file_deleted") is True, f"Expected file_deleted: true, got {data.get('file_deleted')}"
                    assert data.get("error") is not None, "Error message should be provided"

                    # pm2 restart çağrılmış olmalı
                    mock_pm2.assert_called_once_with(["restart", "mavi-baileys-bridge"])

                    # Dosya silinmiş olmalı (pm2 başarısızlığa rağmen)
                    assert not os.path.exists(temp_auth_dir), \
                        "Auth directory should be deleted even if pm2 restart fails"

        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)

    def test_disconnect_partial_success_file_deleted_field(self):
        """
        Given: pm2 restart başarısız, dosya silindi
        When: Response döndürülür
        Then: "file_deleted" alanı var ve True
        """
        valid_token = 'test_disconnect_file_deleted_field_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp(prefix='baileys_test_')

        try:
            with open(os.path.join(temp_auth_dir, 'test.json'), 'w') as f:
                f.write('{}')

            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch.object(admin_panel, '_pm2', return_value=(False, "Restart failed")):
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    data = response.get_json()
                    assert "file_deleted" in data, "Response must contain 'file_deleted' field"
                    assert data["file_deleted"] is True, "file_deleted should be true"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)

    def test_disconnect_partial_success_retry_becomes_idempotent(self):
        """
        Given: Dosya silindi ama pm2 restart başarısız oldu (AC-5 durumu)
        When: Aynı endpoint ikinci kez çağrılırsa
        Then: Klasör yok olduğu için AC-2 (already_logged_out) durumuna düşer
        Bu test, kendi kendine düzelme mekanizmasını doğrular
        """
        valid_token = 'test_disconnect_retry_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp(prefix='baileys_retry_')

        try:
            # İlk çağrı: dosya silinir, pm2 başarısız
            with open(os.path.join(temp_auth_dir, 'creds.json'), 'w') as f:
                f.write('{}')

            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch.object(admin_panel, '_pm2', return_value=(False, "Service not found")) as mock_pm2_1:
                    response1 = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )
                    assert response1.status_code == 500
                    data1 = response1.get_json()
                    assert data1.get("step") == "pm2_restart"

                    # İkinci çağrı: klasör artık yok, pm2 başarılı
                    with patch.object(admin_panel, '_pm2', return_value=(True, "Restarted")) as mock_pm2_2:
                        response2 = admin_panel.app.test_client().post(
                            '/api/whatsapp/disconnect',
                            headers={'Authorization': f'Bearer {valid_token}'}
                        )
                        assert response2.status_code == 200
                        data2 = response2.get_json()
                        assert data2.get("ok") is True
                        assert data2.get("status") == "already_logged_out"
                        # Önceki başarısız pm2 çağrısı yok, bu sefer başarılı
                        mock_pm2_2.assert_called_once_with(["restart", "mavi-baileys-bridge"])

        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)


class TestDisconnectEdgeCases:
    """Edge case tests"""

    def test_disconnect_endpoint_method_not_allowed_get(self):
        """
        Given: /api/whatsapp/disconnect'e GET isteği atılır
        When: Endpoint sadece POST'u desteklerse
        Then: 405 Method Not Allowed döner (veya 404)
        """
        valid_token = 'test_disconnect_method_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        try:
            response = admin_panel.app.test_client().get(
                '/api/whatsapp/disconnect',
                headers={'Authorization': f'Bearer {valid_token}'}
            )
            # 404 (route yok) veya 405 (method not allowed) beklenir
            assert response.status_code in [404, 405], \
                f"Expected 404 or 405 for GET request, got {response.status_code}"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]

    def test_disconnect_with_wrong_auth_scheme(self):
        """
        Given: Authorization header'ı "Basic" veya başka scheme kullanıyor
        When: /api/whatsapp/disconnect çağrılır
        Then: 401 döner
        """
        response = admin_panel.app.test_client().post(
            '/api/whatsapp/disconnect',
            headers={'Authorization': 'Basic dXNlcjpwYXNz'}
        )
        assert response.status_code == 401

    def test_disconnect_response_fields_on_success(self):
        """
        Given: Happy path (başarılı disconnect)
        When: 200 response döner
        Then: response'de en az: ok, status alanları var
        """
        valid_token = 'test_disconnect_fields_success_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp()

        try:
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch.object(admin_panel, '_pm2', return_value=(True, "OK")):
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    data = response.get_json()
                    required_fields = ["ok", "status"]
                    for field in required_fields:
                        assert field in data, f"Missing required field: {field}"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)

    def test_disconnect_response_fields_on_error(self):
        """
        Given: Dosya silme hatası (file_delete step)
        When: 500 response döner
        Then: response'de en az: ok, error, step alanları var
        """
        valid_token = 'test_disconnect_fields_error_' + str(time.time())
        admin_panel.TOKENS[valid_token] = time.time() + 3600

        temp_auth_dir = tempfile.mkdtemp()

        try:
            with patch.object(admin_panel, 'BAILEYS_AUTH_DIR', temp_auth_dir):
                with patch('shutil.rmtree', side_effect=PermissionError("Denied")):
                    response = admin_panel.app.test_client().post(
                        '/api/whatsapp/disconnect',
                        headers={'Authorization': f'Bearer {valid_token}'}
                    )

                    data = response.get_json()
                    required_error_fields = ["ok", "error", "step"]
                    for field in required_error_fields:
                        assert field in data, f"Missing required field in error response: {field}"
        finally:
            if valid_token in admin_panel.TOKENS:
                del admin_panel.TOKENS[valid_token]
            if os.path.exists(temp_auth_dir):
                shutil.rmtree(temp_auth_dir, ignore_errors=True)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
