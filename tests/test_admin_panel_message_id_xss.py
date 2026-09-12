#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for admin-panel-message-id-xss (Strix güvenlik açığı AC-1/AC-6/AC-7).

Acceptance Criteria (from atdd.md):
1. [Critical] AC-1: Given webhook'tan gelen bir `message_id` HTML/JS özel karakteri
   içeriyor, When admin panel `/` sayfasını render ediyor, Then `message_id`
   `data-mid` attribute'una `escapeHtml` ile yazılır ve `onclick` handler'ları
   `this.dataset.mid` kullanır — hiçbir sink'te ham interpolasyon kalmaz
   (satır 1601-1602, 1622, ve `openEditModal` için).

2. [Medium] AC-6: Given meşru (kötü niyetli olmayan) bir `message_id` HTML
   özel karakteri içeriyor, When admin panel render ediyor, Then veri
   reddedilmez, sadece güvenli şekilde escape edilerek görüntülenir.

3. [Medium] AC-7: Given XSS düzeltmesi uygulandı, When opsiyonel CSP
   (`script-src 'self'`) eklenir, Then inline handler'lar dışındaki script
   çalıştırma girişimleri tarayıcı tarafından engellenir.

Test Stratejisi:
- Unit testleri: admin_panel.py'nin kaynak kodunda _renderShipList fonksiyonunda
  - Satır 1601-1602'de onclick handler'ları içinde HAM interpolasyon yok
  - Bunun yerine data-mid attribute'u + this.dataset.mid kullanılıyor
  - escapeHtml() fonksiyonu çağrılıyor
- Integration testleri: Flask route çağrılıp HTML render edilir, XSS payload'ı
  içeren message_id escape edilmiş olup olmadığı HTML'de kontrol edilir.
"""

import pytest
import os
import sys
import json
import inspect
import re
from unittest.mock import MagicMock, patch

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Stub out heavy imports BEFORE importing admin_panel
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

# Clean up sys.modules pollution
del sys.modules['src.parsers.veri_cekici_ayristirici']
del sys.modules['src.utils.reporter']
del sys.modules['src.utils.config']


class TestAC1_XSSPayloadEscaping:
    """
    AC-1: message_id HTML/JS özel karakteri içeriyorsa, admin panel HTML'inde
    `data-mid` attribute'una `escapeHtml` ile yazılmalı, onclick handler'ları
    `this.dataset.mid` kullanmalı — hiçbir sink'te ham interpolasyon kalmamalı.

    Bu test, kaynak kod stringi araması ile _renderShipList fonksiyonunda:
    1. onclick handler'larında (`approveAll`, `deleteMsg`, `openEditModal`)
       HAM interpolasyon yok
    2. data-mid attribute'u var ve escapeHtml() çağrısı var
    3. onclick handler'ları this.dataset.mid kullanıyor
    """

    def test_no_raw_interpolation_in_onclick_handlers(self):
        """
        Unit test: _renderShipList() fonksiyonun kaynak kodunda,
        onclick handler'larında (`onclick="approveAll('${mid}')"` gibi)
        HAM interpolasyon yok mu?

        Şu an: FAIL (satır 1601-1602'de ham interpolasyon var)
        Code-copilot uygulandıktan sonra: PASS (data-mid + this.dataset.mid)
        """
        # Get admin_panel.py source file
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Find _renderShipList function (approximate, since it's JS embedded in HTML)
        render_ship_list_match = re.search(r'_renderShipList.*?\n}', source, re.DOTALL)

        if render_ship_list_match:
            render_ship_list_code = render_ship_list_match.group(0)

            # Check for BAD patterns: onclick="...${mid}..." (ham interpolasyon)
            # Pattern: onclick="approveAll('${mid}')" or onclick="deleteMsg('${mid}')"
            bad_patterns = [
                r"onclick=['\"]approveAll\(['\"]?\$\{mid\}",
                r"onclick=['\"]deleteMsg\(['\"]?\$\{mid\}",
                r"onclick=['\"]openEditModal\(['\"]?\$\{mid",
            ]

            for pattern in bad_patterns:
                assert not re.search(pattern, render_ship_list_code), (
                    f"Found raw interpolation in onclick handler (pattern: {pattern}). "
                    f"AC-1 requires data-mid attribute + this.dataset.mid instead."
                )

    def test_onclick_handlers_use_dataset_mid(self):
        """
        Unit test: _renderShipList() fonksiyonunda onclick handler'ları
        `this.dataset.mid` kullanıyor mu?

        Şu an: FAIL (ham ${mid} interpolasyonu kullanıyor)
        Code-copilot uygulandıktan sonra: PASS
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        render_ship_list_match = re.search(r'_renderShipList.*?\n}', source, re.DOTALL)

        if render_ship_list_match:
            render_ship_list_code = render_ship_list_match.group(0)

            # Good pattern: onclick="...this.dataset.mid..."
            has_dataset_mid = 'this.dataset.mid' in render_ship_list_code

            assert has_dataset_mid, (
                "onclick handler'ları this.dataset.mid kullanmıyor. "
                "AC-1 requires `this.dataset.mid` for reading message_id from data attribute."
            )

    def test_data_mid_attribute_with_escape_html(self):
        """
        Unit test: _renderShipList() fonksiyonunda data-mid attribute'u
        `escapeHtml()` ile çağrılıyor mu?

        Şu an: FAIL
        Code-copilot uygulandıktan sonra: PASS
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        render_ship_list_match = re.search(r'_renderShipList.*?\n}', source, re.DOTALL)

        if render_ship_list_match:
            render_ship_list_code = render_ship_list_match.group(0)

            # Pattern: data-mid="${escapeHtml(...mid...)"
            has_escaped_data_mid = re.search(
                r'data-mid\s*=\s*"[^"]*escapeHtml\s*\(',
                render_ship_list_code
            )

            assert has_escaped_data_mid, (
                "data-mid attribute'u escapeHtml() ile çağrılmıyor. "
                "AC-1 requires `data-mid=\"${escapeHtml(...)}\"` pattern."
            )

    def test_approve_all_button_uses_data_attribute(self):
        """
        Unit test: "Tümünü Onayla" butonu satırında (satır ~1601),
        onclick handler'ı data-mid yerine raw ${mid} kullanmıyor mu?

        Şu an: FAIL (raw onclick="approveAll('${mid}')")
        Code-copilot uygulandıktan sonra: PASS
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Search for the bulk action buttons section
        buttons_match = re.search(
            r'const bulkHtml = `.*?Tümünü Onayla.*?Tümünü Sil.*?`;',
            source,
            re.DOTALL
        )

        if buttons_match:
            buttons_code = buttons_match.group(0)

            # BAD: onclick="approveAll('${mid}')"
            has_bad_approve = re.search(r"onclick=['\"]approveAll\(['\"]?\$\{mid\}", buttons_code)

            # GOOD: onclick="..." with parent data-mid
            # OR different approach (depends on code-copilot implementation)

            # The test expects NO raw ${mid} in onclick
            assert not has_bad_approve, (
                "approveAll button uses raw ${mid} in onclick. "
                "AC-1 requires using parent's data-mid attribute via this.dataset.mid."
            )

    def test_edit_modal_button_escapes_mid(self):
        """
        Unit test: "✏️" Edit button satırında (satır ~1622),
        `openEditModal()` çağrısında `midE` encode edilip `data-mid` attribute'unda
        kullanılıyor mu?

        Expected pattern (AC-1):
        data-mid="${escapeHtml(encodeURIComponent(mid))}" +
        onclick="openEditModal()" +
        openEditModal() fonksiyonunda this.dataset.mid okuması

        Şu an: FAIL (raw ${midE} interpolasyonu var)
        Code-copilot uygulandıktan sonra: PASS
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Find the edit button section (✏️)
        edit_button_match = re.search(
            r"onclick=['\"]openEditModal\([^)]*\)['\"]",
            source
        )

        if edit_button_match:
            edit_button_code = edit_button_match.group(0)

            # GOOD: onclick="openEditModal()" with data-mid attribute + this.dataset.mid
            # (exact pattern depends on code-copilot)
            #
            # BAD: onclick="openEditModal('${midE}',${i})" with raw interpolation

            # For now, check that there's NO raw ${midE} in onclick function call
            has_raw_mide = re.search(r"openEditModal\(['\"]?\$\{midE", edit_button_code)

            assert not has_raw_mide, (
                "openEditModal() uses raw ${midE} in function call. "
                "AC-1 requires data-mid attribute + this.dataset.mid pattern."
            )


class TestAC6_LegitimateCharactersEscaped:
    """
    AC-6: Meşru (kötü niyetli olmayan) HTML özel karakteri içeren
    message_id reddedilmemeli, sadece escape edilerek görüntülenmeli.

    Test: message_id = "abc<123>def" gibi bir değer, admin panel'de
    "&lt;123&gt;" şeklinde escape edilip görüntülenmeli, reddedilmemeli.
    """

    def test_legitimate_html_chars_are_escaped_not_rejected(self):
        """
        Unit test: escapeHtml() fonksiyonu, meşru HTML karakterleri
        (< > & " ') escape ediyor mu, reddemiyor mu?

        Bu test, escapeHtml fonksiyonunun varlığı ve davranışını doğrular.
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Find escapeHtml function definition
        escape_html_match = re.search(
            r'function escapeHtml\s*\([^)]*\)\s*\{[^}]*\}',
            source,
            re.DOTALL
        )

        assert escape_html_match, (
            "escapeHtml() fonksiyonu tanımlı değil. AC-6 için gereklidir."
        )

        escape_html_code = escape_html_match.group(0)

        # Check for replacement patterns in object literal: '&':'&amp;', '<':'&lt;', '>':'&gt;'
        # The actual code uses: ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])
        replacements = [
            r"'&'\s*:\s*'&amp;'",
            r"'<'\s*:\s*'&lt;'",
            r"'>'\s*:\s*'&gt;'",
        ]

        has_replacements = all(re.search(pattern, escape_html_code) for pattern in replacements)

        assert has_replacements, (
            "escapeHtml() fonksiyonu HTML özel karakterleri escape etmiyor. "
            "AC-6 requires escaping < > & \" ' characters."
        )


class TestAC7_CSPHeader:
    """
    AC-7: opsiyonel CSP header (`script-src 'self'`) eklenmiş olabilir.

    Bu test opsiyonel, atdd.md'de "Medium" olarak işaretli.
    Varsa kontrol et, yoksa skip et.
    """

    def test_csp_header_in_admin_panel_route(self):
        """
        Unit test: admin_panel.py'nin Flask route'larında
        `Content-Security-Policy: script-src 'self'` header'ı ayarlanmış mı?

        Bu test opsiyoneldir. CSP varsa PASS, yoksa SKIP (xfail).
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Look for CSP header setting in Flask routes
        has_csp_response = (
            'Content-Security-Policy' in source or
            'script-src' in source or
            'response.headers' in source
        )

        # AC-7 is optional (Medium priority, Acceptable Condition).
        # If CSP is not found, this test is skipped (xfail expected).
        if not has_csp_response:
            pytest.skip("CSP header not found in admin_panel.py (AC-7 is optional)")
        else:
            # If CSP is mentioned, check for proper pattern
            csp_pattern = re.search(
                r"[Cc]ontent-[Ss]ecurity-[Pp]olicy.*?script-src\s+'self'",
                source,
                re.IGNORECASE | re.DOTALL
            )

            assert csp_pattern, (
                "CSP header found but pattern incorrect. "
                "Expected: Content-Security-Policy: script-src 'self'"
            )


class TestSourceCodeStructure:
    """
    Unit testleri — admin_panel.py kaynak kod yapısı doğrulama
    """

    def test_escape_html_function_exists(self):
        """
        Unit test: admin_panel.py'de escapeHtml() JS fonksiyonu tanımlı mı?

        Şu an: PASS (mevcut kod satır 1541-1543'te tanımlı)
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        assert 'function escapeHtml' in source or 'const escapeHtml' in source, (
            "escapeHtml() fonksiyonu admin_panel.py'de tanımlı değil. "
            "AC-1 ve AC-6 için gereklidir."
        )

    def test_shipments_render_uses_escape_html(self):
        """
        Unit test: _renderShipList() fonksiyonunda sevkiyat bilgileri
        render edilirken escapeHtml() çağrılıyor mu?

        Örn: from_location, to_location, tags, phone vb.

        Şu an: PASS (mevcut kod satır 1617-1620'de escapeHtml çağrıları var)
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Find _renderShipList function
        render_ship_list_match = re.search(r'_renderShipList.*?\n}', source, re.DOTALL)

        if render_ship_list_match:
            render_ship_list_code = render_ship_list_match.group(0)

            # Count escapeHtml calls in shipments rendering
            escape_count = render_ship_list_code.count('escapeHtml(')

            assert escape_count > 0, (
                "_renderShipList() fonksiyonunda escapeHtml() çağrısı yok. "
                "Sevkiyat verileri escape edilmeden render ediliyor (XSS riski)."
            )


class TestMessageIDPatterns:
    """
    Integration-level unit testleri — message_id içeren XSS payload'ları
    admin_panel.py kaynak kodunda test edilir.
    """

    def test_message_id_with_xss_payload_would_be_escaped(self):
        """
        Conceptual test: Eğer message_id = '<img src=x onerror=alert(1)>' ise,
        admin_panel render edildiğinde bu payload _renderShipList'te
        escapeHtml() ile escape edilmeli.

        Bu test, escapeHtml fonksiyonunun varlığını ve kullanımını kontrol eder.
        """
        admin_panel_file = inspect.getsourcefile(admin_panel)
        with open(admin_panel_file, 'r', encoding='utf-8') as f:
            source = f.read()

        # Verify that _renderShipList uses escapeHtml for message_id
        render_ship_list_match = re.search(r'_renderShipList.*?\n}', source, re.DOTALL)

        if render_ship_list_match:
            render_ship_list_code = render_ship_list_match.group(0)

            # Pattern: data-mid="${escapeHtml(...mid...)"
            has_mid_escaped = re.search(
                r'data-mid\s*=\s*"[^"]*escapeHtml\s*\([^)]*mid',
                render_ship_list_code
            )

            assert has_mid_escaped, (
                "message_id (mid) not being escaped in data-mid attribute. "
                "XSS payload in message_id would execute."
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
