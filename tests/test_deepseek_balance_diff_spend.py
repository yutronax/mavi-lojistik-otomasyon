#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for deepseek-balance-diff-maliyet-hesaplama.

Reference: obss_project/artifacts/deepseek-balance-diff-maliyet-hesaplama/atdd.md

Acceptance Criteria:
1. [Critical] Ardışık iki başarılı okuma arasındaki fark, gerçek harcama
   olarak deepseek_balance_history.json'a eklenir.
2. [Critical] Balance ARTMIŞSA (top-up), negatif fark asla "harcama" olarak
   yazılmaz — spend_usd=0 + top_up_detected=True.
3. [Critical] Bir okuma "unknown" ise, o pencere gap=True olarak işaretlenir,
   spend_usd yazılmaz (None); bir sonraki okuma en son BİLİNEN başarılı
   balance ile karşılaştırılır (ara "unknown" okumalar referansı bozmaz).
4. [High] İlk okuma (referans yok) için hiçbir history kaydı eklenmez.
5. [High] /api/status yeni bir deepseek_real_spend alanı döner; mevcut
   deepseek_balance alanı DEĞİŞMEZ.

Test Technique: admin_panel._compute_balance_diff, _append_deepseek_balance_history,
_load_last_known_deepseek_balance saf/dosya fonksiyonları izole test edilir.
Sonsuz döngü (_refresh_deepseek_balance'ın while True'su) DOĞRUDAN test edilmez.
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.getcwd())

# Mock google.genai before importing admin_panel's dependency chain
sys.modules.setdefault('google', MagicMock())
sys.modules.setdefault('google.genai', MagicMock())

from src.api import admin_panel


# ---------------- AC-1, AC-2, AC-3, AC-4: _compute_balance_diff (pure function) ----------------

class TestComputeBalanceDiff:
    def test_happy_path_balance_decreased_returns_spend(self):
        """AC-1: prev=10.00, curr=9.75 -> spend=0.25, gap=False, top_up_detected=False."""
        curr_result = {"available": True, "balance_usd": 9.75, "low": False}
        entry = admin_panel._compute_balance_diff(
            prev_balance=10.00, curr_result=curr_result,
            t_prev="2026-09-09T10:00:00", t_curr="2026-09-09T10:15:00",
        )
        assert entry is not None
        assert entry["spend_usd"] == pytest.approx(0.25)
        assert entry["gap"] is False
        assert entry["top_up_detected"] is False
        assert entry["balance_prev"] == 10.00
        assert entry["balance_curr"] == 9.75

    def test_balance_increased_top_up_detected_spend_zero(self):
        """AC-2: prev=9.75, curr=12.00 (top-up) -> spend=0 (NEVER negative), top_up_detected=True."""
        curr_result = {"available": True, "balance_usd": 12.00, "low": False}
        entry = admin_panel._compute_balance_diff(
            prev_balance=9.75, curr_result=curr_result,
            t_prev="2026-09-09T10:15:00", t_curr="2026-09-09T10:30:00",
        )
        assert entry is not None
        assert entry["spend_usd"] == 0.0
        assert entry["top_up_detected"] is True
        assert entry["gap"] is False

    def test_balance_unchanged_no_top_up_no_spend(self):
        """Boş sonuç ↔ hata ayrımı: gerçekten hiç harcama olmamış (fark=0) top_up=False olmalı,
        bu 'gap' (bilinmiyor) durumuyla KARIŞTIRILMAMALI."""
        curr_result = {"available": True, "balance_usd": 10.00, "low": False}
        entry = admin_panel._compute_balance_diff(
            prev_balance=10.00, curr_result=curr_result,
            t_prev="2026-09-09T10:00:00", t_curr="2026-09-09T10:15:00",
        )
        assert entry["spend_usd"] == 0.0
        assert entry["top_up_detected"] is False
        assert entry["gap"] is False

    def test_unknown_reading_marks_gap_no_spend_written(self):
        """AC-3: curr "unknown" (ağ hatası) -> gap=True, spend_usd=None (0 YAZILMAZ)."""
        curr_result = {"available": "unknown", "balance_usd": None, "low": False}
        entry = admin_panel._compute_balance_diff(
            prev_balance=10.00, curr_result=curr_result,
            t_prev="2026-09-09T10:00:00", t_curr="2026-09-09T10:15:00",
        )
        assert entry is not None
        assert entry["gap"] is True
        assert entry["spend_usd"] is None
        assert entry["top_up_detected"] is False

    def test_first_reading_no_previous_balance_returns_none(self):
        """AC-4: prev_balance=None (hiç referans yok, ilk okuma) -> hiçbir kayıt üretilmez (None)."""
        curr_result = {"available": True, "balance_usd": 10.00, "low": False}
        entry = admin_panel._compute_balance_diff(
            prev_balance=None, curr_result=curr_result,
            t_prev=None, t_curr="2026-09-09T10:00:00",
        )
        assert entry is None

    def test_unknown_reading_with_no_previous_balance_still_returns_none(self):
        """Edge: ilk okumanın kendisi 'unknown' ise de referans yok, kayıt YAZILMAZ
        (gap yazmanın anlamı yok, karşılaştıracak hiçbir şey yoktu)."""
        curr_result = {"available": "unknown", "balance_usd": None, "low": False}
        entry = admin_panel._compute_balance_diff(
            prev_balance=None, curr_result=curr_result,
            t_prev=None, t_curr="2026-09-09T10:00:00",
        )
        assert entry is None


# ---------------- AC-1, AC-3: history persistence + restart recovery ----------------

class TestAppendAndLoadHistory:
    def test_append_creates_file_and_appends_entries(self, tmp_path):
        """AC-1: _append_deepseek_balance_history yeni dosya oluşturur ve append eder (üzerine yazmaz)."""
        history_path = tmp_path / "deepseek_balance_history.json"
        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(history_path)):
            entry1 = {"t_prev": "t0", "t_curr": "t1", "balance_prev": 10.0,
                      "balance_curr": 9.75, "spend_usd": 0.25, "top_up_detected": False, "gap": False}
            entry2 = {"t_prev": "t1", "t_curr": "t2", "balance_prev": 9.75,
                      "balance_curr": 9.50, "spend_usd": 0.25, "top_up_detected": False, "gap": False}
            admin_panel._append_deepseek_balance_history(entry1)
            admin_panel._append_deepseek_balance_history(entry2)

            assert history_path.exists()
            data = json.loads(history_path.read_text(encoding="utf-8"))
            assert data == [entry1, entry2]

    def test_load_last_known_balance_skips_gap_entries(self, tmp_path):
        """AC-3: en son bilinen (gap=False) balance okunur, ara 'gap' kayıtları atlanır —
        yani bir 'unknown' okuma referansı BOZMAZ."""
        history_path = tmp_path / "deepseek_balance_history.json"
        history_path.write_text(json.dumps([
            {"t_prev": "t0", "t_curr": "t1", "balance_prev": 10.0, "balance_curr": 9.75,
             "spend_usd": 0.25, "top_up_detected": False, "gap": False},
            {"t_prev": "t1", "t_curr": "t2", "balance_prev": 9.75, "balance_curr": None,
             "spend_usd": None, "top_up_detected": False, "gap": True},
        ]), encoding="utf-8")

        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(history_path)):
            balance, ts = admin_panel._load_last_known_deepseek_balance()
            assert balance == 9.75
            assert ts == "t1"

    def test_load_last_known_balance_missing_file_returns_none(self, tmp_path):
        """AC-4: dosya yoksa (ilk çalıştırma) (None, None) döner — hata fırlatılmaz."""
        history_path = tmp_path / "does_not_exist.json"
        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(history_path)):
            balance, ts = admin_panel._load_last_known_deepseek_balance()
            assert balance is None
            assert ts is None

    def test_append_write_failure_does_not_raise(self, tmp_path, caplog):
        """Kısmi başarı: disk/izin hatası history yazmayı engellerse, exception
        DIŞARI SIZMAMALI (arka plan thread'ini crash ettirmemeli) — sadece loglanır."""
        bad_path = tmp_path / "no_such_dir" / "deepseek_balance_history.json"
        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(bad_path)):
            with patch("os.replace", side_effect=OSError("disk full")):
                # Should not raise
                admin_panel._append_deepseek_balance_history({"gap": True})


# ---------------- AC-5: /api/status yeni alan, mevcut alan DEĞİŞMEZ ----------------

class TestStatusEndpointRealSpend:
    def test_status_includes_deepseek_real_spend_field(self):
        """AC-5: /api/status yanıtı deepseek_real_spend alanını içerir, mevcut
        deepseek_balance alanı DEĞİŞMEDEN kalır."""
        mock_status_cache = {"service": {"status": "running"}, "system": None}
        mock_deepseek_balance_cache = {"available": True, "balance_usd": 8.75, "low": False}

        with patch.object(admin_panel, "_status_cache", mock_status_cache):
            with patch.object(admin_panel, "_deepseek_balance_cache", mock_deepseek_balance_cache):
                with patch.object(admin_panel, "_get_deepseek_real_spend", return_value=0.25):
                    with admin_panel.app.test_request_context():
                        response = admin_panel.status.__wrapped__()
                        data = response.get_json() if hasattr(response, "get_json") else json.loads(response[0])

                    assert data["deepseek_balance"] == mock_deepseek_balance_cache, (
                        "Mevcut deepseek_balance alanı DEĞİŞMEMELİ"
                    )
                    assert data["deepseek_real_spend"] == 0.25

    def test_get_deepseek_real_spend_returns_none_when_no_history(self, tmp_path):
        """Hiç history kaydı yoksa (henüz ilk okuma bile yapılmamış) None döner,
        0 YAZILMAZ (0 ile 'veri yok' karışmamalı)."""
        history_path = tmp_path / "deepseek_balance_history.json"
        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(history_path)):
            assert admin_panel._get_deepseek_real_spend() is None

    def test_get_deepseek_real_spend_returns_none_when_last_entry_is_gap(self, tmp_path):
        """Son kayıt gap=True ise (son pencere 'bilinmiyor') None döner, 0 YAZILMAZ."""
        history_path = tmp_path / "deepseek_balance_history.json"
        history_path.write_text(json.dumps([
            {"t_prev": "t0", "t_curr": "t1", "balance_prev": 10.0, "balance_curr": None,
             "spend_usd": None, "top_up_detected": False, "gap": True},
        ]), encoding="utf-8")
        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(history_path)):
            assert admin_panel._get_deepseek_real_spend() is None

    def test_get_deepseek_real_spend_returns_last_entry_spend(self, tmp_path):
        history_path = tmp_path / "deepseek_balance_history.json"
        history_path.write_text(json.dumps([
            {"t_prev": "t0", "t_curr": "t1", "balance_prev": 10.0, "balance_curr": 9.75,
             "spend_usd": 0.25, "top_up_detected": False, "gap": False},
            {"t_prev": "t1", "t_curr": "t2", "balance_prev": 9.75, "balance_curr": 9.50,
             "spend_usd": 0.25, "top_up_detected": False, "gap": False},
        ]), encoding="utf-8")
        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(history_path)):
            assert admin_panel._get_deepseek_real_spend() == 0.25


# ---------------- Restart kurtarma: mevcut ai_spend_history.json desenine paralel ----------------

class TestRestartRecoveryPattern:
    def test_load_last_known_balance_used_as_restart_reference(self, tmp_path):
        """Plan.md: PM2 restart sonrası _load_last_known_deepseek_balance() dosyadaki
        son (gap olmayan) kaydı referans olarak döner — text_gen_parser.py'nin
        _init_hourly_counter_from_file() ile aynı desen."""
        history_path = tmp_path / "deepseek_balance_history.json"
        history_path.write_text(json.dumps([
            {"t_prev": "t0", "t_curr": "t1", "balance_prev": 10.0, "balance_curr": 9.75,
             "spend_usd": 0.25, "top_up_detected": False, "gap": False},
        ]), encoding="utf-8")
        with patch.object(admin_panel, "DEEPSEEK_BALANCE_HISTORY_PATH", str(history_path)):
            balance, ts = admin_panel._load_last_known_deepseek_balance()
            # Yeni bir _compute_balance_diff çağrısı bu referansla karşılaştırma yapabilmeli
            curr_result = {"available": True, "balance_usd": 9.60, "low": False}
            entry = admin_panel._compute_balance_diff(
                prev_balance=balance, curr_result=curr_result, t_prev=ts, t_curr="t2",
            )
            assert entry is not None
            assert entry["spend_usd"] == pytest.approx(0.15)
