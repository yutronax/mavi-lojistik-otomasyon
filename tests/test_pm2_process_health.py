#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for pm2-process-izleme-ve-uyari.

Reference: obss_project/artifacts/pm2-process-izleme-ve-uyari/atdd.md

Bugünkü canlı olay: mavi-baileys-bridge PM2 listesinden TAMAMEN düşmüştü
(crash-loop değil, pm2 jlist çıktısında hiç görünmüyordu). Kullanıcı bunu
manuel fark etti. Mevcut _refresh_status_cache SADECE SERVICE_NAME
(mavi-lojistik-server) tek process'ini izliyordu, diğer ikisi hiç kontrol
edilmiyordu.

Acceptance Criteria:
1. [Critical] 3 process de online -> process_health hepsi "ok", bildirim yok.
2. [Critical] Bir process down (ilk tespit) -> process_health "down" +
   down_since damgası.
3. [Critical] Aynı process hâlâ down (debounce penceresi) -> down_since
   DEĞİŞMEZ (ilk tespit zamanı korunur).
4. [High] Down process tekrar online -> "ok", down_since temizlenir.
5. [High] pm2 jlist komutu tamamen başarısız -> TÜM process'ler "unknown"
   (down DEĞİL), sessiz "her şey online" izlenimi verilmez.

Test Technique: admin_panel._compute_process_health (saf fonksiyon) ve
admin_panel._parse_pm2_jlist (I/O ayrıştırma) izole test edilir. Arka plan
thread'i (_refresh_status_cache'in while True'su) DOĞRUDAN test edilmez.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.getcwd())

sys.modules.setdefault('google', MagicMock())
sys.modules.setdefault('google.genai', MagicMock())

from src.api import admin_panel


# ---------------- AC-1..4: _compute_process_health (pure function) ----------------

class TestComputeProcessHealth:
    def test_all_online_returns_ok_no_down_since(self):
        """AC-1: 3 process de 'online' -> hepsi 'ok', down_since None."""
        pm2_processes = {
            "mavi-lojistik-server": "online",
            "mavi-admin-panel": "online",
            "mavi-baileys-bridge": "online",
        }
        result = admin_panel._compute_process_health(pm2_processes, previous_health={}, now_iso="t1")

        assert set(result.keys()) == {"mavi-lojistik-server", "mavi-admin-panel", "mavi-baileys-bridge"}
        for name, info in result.items():
            assert info["status"] == "ok", f"{name} should be ok"
            assert info["down_since"] is None

    def test_missing_process_treated_as_down(self):
        """AC-2: bir process pm2 jlist çıktısında HİÇ YOK (bugünkü canlı olay) -> 'down'."""
        pm2_processes = {
            "mavi-lojistik-server": "online",
            "mavi-admin-panel": "online",
            # mavi-baileys-bridge tamamen eksik
        }
        result = admin_panel._compute_process_health(pm2_processes, previous_health={}, now_iso="t1")

        assert result["mavi-baileys-bridge"]["status"] == "down"
        assert result["mavi-baileys-bridge"]["down_since"] == "t1"

    def test_stopped_status_treated_as_down(self):
        """AC-2: process listede var ama status 'online' değil (ör. 'stopped') -> 'down'."""
        pm2_processes = {
            "mavi-lojistik-server": "online",
            "mavi-admin-panel": "online",
            "mavi-baileys-bridge": "stopped",
        }
        result = admin_panel._compute_process_health(pm2_processes, previous_health={}, now_iso="t1")

        assert result["mavi-baileys-bridge"]["status"] == "down"
        assert result["mavi-baileys-bridge"]["down_since"] == "t1"

    def test_down_since_preserved_across_repeated_down_checks(self):
        """AC-3: process hâlâ down ise down_since İLK TESPİT zamanında sabit kalır
        (debounce altyapısı — spam'i önlemek için ne zamandan beri down olduğu bilinmeli)."""
        previous_health = {
            "mavi-lojistik-server": {"status": "ok", "down_since": None},
            "mavi-admin-panel": {"status": "ok", "down_since": None},
            "mavi-baileys-bridge": {"status": "down", "down_since": "t1"},
        }
        pm2_processes = {
            "mavi-lojistik-server": "online",
            "mavi-admin-panel": "online",
            # hâlâ eksik
        }
        result = admin_panel._compute_process_health(pm2_processes, previous_health, now_iso="t2")

        assert result["mavi-baileys-bridge"]["status"] == "down"
        assert result["mavi-baileys-bridge"]["down_since"] == "t1", (
            "down_since ilk tespit zamanında sabit kalmalı, t2'ye GÜNCELLENMEMELİ"
        )

    def test_recovered_process_clears_down_since(self):
        """AC-4: down process tekrar online olursa -> 'ok', down_since temizlenir."""
        previous_health = {
            "mavi-lojistik-server": {"status": "ok", "down_since": None},
            "mavi-admin-panel": {"status": "ok", "down_since": None},
            "mavi-baileys-bridge": {"status": "down", "down_since": "t1"},
        }
        pm2_processes = {
            "mavi-lojistik-server": "online",
            "mavi-admin-panel": "online",
            "mavi-baileys-bridge": "online",
        }
        result = admin_panel._compute_process_health(pm2_processes, previous_health, now_iso="t2")

        assert result["mavi-baileys-bridge"]["status"] == "ok"
        assert result["mavi-baileys-bridge"]["down_since"] is None

    def test_recovered_then_down_again_resets_down_since(self):
        """AC-3/AC-4 zincirleme: down -> online (düzeldi, down_since temizlendi) ->
        tekrar down olursa down_since YENİDEN başlamalı (eski down_since'e YAPIŞMAMALI)."""
        previous_health = {
            "mavi-lojistik-server": {"status": "ok", "down_since": None},
            "mavi-admin-panel": {"status": "ok", "down_since": None},
            "mavi-baileys-bridge": {"status": "ok", "down_since": None},  # az önce düzelmişti
        }
        pm2_processes = {
            "mavi-lojistik-server": "online",
            "mavi-admin-panel": "online",
            # tekrar düştü
        }
        result = admin_panel._compute_process_health(pm2_processes, previous_health, now_iso="t3")

        assert result["mavi-baileys-bridge"]["status"] == "down"
        assert result["mavi-baileys-bridge"]["down_since"] == "t3", (
            "önceki düşüşten kalan eski down_since'e yapışmamalı, yeni düşüşün zamanı olmalı"
        )

    def test_pm2_command_failed_marks_all_unknown_not_down(self):
        """AC-5: pm2_processes=None (subprocess/parse başarısız) -> TÜM process'ler
        'unknown' (down DEĞİL) — sessiz 'her şey online' izlenimi de verilmez."""
        previous_health = {
            "mavi-lojistik-server": {"status": "ok", "down_since": None},
            "mavi-admin-panel": {"status": "down", "down_since": "t1"},
            "mavi-baileys-bridge": {"status": "ok", "down_since": None},
        }
        result = admin_panel._compute_process_health(None, previous_health, now_iso="t2")

        for name, info in result.items():
            assert info["status"] == "unknown", f"{name} pm2 hatasında 'unknown' olmalı, 'down' veya 'ok' değil"
            assert info["down_since"] is None

    def test_first_check_with_no_previous_history_down_process(self):
        """Edge: hiç previous_health yokken (ilk kontrol, process_health henüz boş)
        bir process down ise down_since=now_iso olur, KeyError fırlatmaz."""
        result = admin_panel._compute_process_health(
            {"mavi-lojistik-server": "online"}, previous_health={}, now_iso="t1"
        )
        assert result["mavi-admin-panel"]["status"] == "down"
        assert result["mavi-admin-panel"]["down_since"] == "t1"


# ---------------- pm2 jlist parse helper ----------------

class TestParsePm2Jlist:
    def test_parses_valid_jlist_output(self):
        """pm2 jlist bazen JSON'dan önce gürültü metni basar (mevcut _refresh_status_cache
        deseniyle aynı: out.find('[') ile JSON başlangıcı bulunur)."""
        raw = 'some noise before json\n' + json.dumps([
            {"name": "mavi-lojistik-server", "pm2_env": {"status": "online"}},
            {"name": "mavi-admin-panel", "pm2_env": {"status": "online"}},
        ])
        result = admin_panel._parse_pm2_jlist(True, raw)
        assert result == {"mavi-lojistik-server": "online", "mavi-admin-panel": "online"}

    def test_subprocess_failure_returns_none(self):
        """pm2 komutu başarısız (ok=False) -> None döner (unknown durumuna düşürülecek)."""
        result = admin_panel._parse_pm2_jlist(False, "some error output")
        assert result is None

    def test_malformed_json_returns_none(self):
        """ok=True ama çıktı bozuk JSON -> None döner, exception fırlatmaz."""
        result = admin_panel._parse_pm2_jlist(True, "not valid json at all {{{")
        assert result is None

    def test_empty_output_returns_none(self):
        result = admin_panel._parse_pm2_jlist(True, "")
        assert result is None


# ---------------- AC-1: /api/status yeni process_health alanı ----------------

class TestStatusEndpointProcessHealth:
    def test_status_includes_process_health_field(self):
        """/api/status yanıtı process_health alanını içerir, mevcut alanlar DEĞİŞMEZ."""
        mock_status_cache = {"service": {"status": "online"}, "system": None}
        mock_process_health = {
            "mavi-lojistik-server": {"status": "ok", "down_since": None},
            "mavi-admin-panel": {"status": "ok", "down_since": None},
            "mavi-baileys-bridge": {"status": "down", "down_since": "2026-09-11T15:00:00"},
        }
        mock_deepseek_balance_cache = {"available": True, "balance_usd": 8.75, "low": False}

        with patch.object(admin_panel, "_status_cache", mock_status_cache):
            with patch.object(admin_panel, "_process_health", mock_process_health):
                with patch.object(admin_panel, "_deepseek_balance_cache", mock_deepseek_balance_cache):
                    with patch.object(admin_panel, "_get_deepseek_real_spend", return_value=None):
                        with admin_panel.app.test_request_context():
                            response = admin_panel.status.__wrapped__()
                            data = response.get_json() if hasattr(response, "get_json") else json.loads(response[0])

                        assert data["process_health"] == mock_process_health
                        assert data["service"] == mock_status_cache["service"], "mevcut alan DEĞİŞMEMELİ"
