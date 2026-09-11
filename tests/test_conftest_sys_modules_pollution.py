#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test suite for test-sys-modules-izolasyon-korumasi.

Reference: obss_project/artifacts/test-sys-modules-izolasyon-korumasi/atdd.md

Bugünkü canlı olay: tests/test_webhook_server_threading.py'de
sys.modules['src.parsers.veri_cekici_ayristirici'] bir MagicMock ile
değiştirilip hiç geri alınmamıştı. Pytest collection aşamasında tüm test
dosyalarını import ettiği için bu, tüm sürecin paylaştığı sys.modules
cache'ini kalıcı kirletti — test_junk_message_filter.py ve
test_hourly_spend_cap.py (7 test) aylarca "Got: MagicMock" hatasıyla fail
etti. monkeypatch mimari olarak collection-time mock'lar için kullanılamaz
(sadece fonksiyon/fixture içinde çalışır) — çözüm "otomatik restore" değil
"TESPİT": tests/conftest.py'deki pytest_collection_finish hook'u collection
bitince sys.modules'taki proje-kendi modüllerinin gerçek mi mock mu
olduğunu kontrol edip kirlilik varsa pytest'i hemen, açık bir mesajla
durdurur.

Acceptance Criteria:
1. [Critical] Hiçbir proje modülü kirli değilse -> hiç uyarı/hata yok.
2. [Critical] Bir proje modülü kirli (MagicMock kalmış) -> hook tespit
   edip hangi modül olduğunu belirten mesajla pytest'i durdurur.
3. [Critical] Fonksiyon içi geçici monkeypatch (test bitince otomatik
   geri alınmış) -> YANLIŞLIKLA kirlilik sayılmaz.
4. [High] Birden fazla modül kirli -> TÜMÜ tek mesajda listelenir.
5. [High] Proje modülü sys.modules'ta hiç yok (henüz import edilmemiş)
   -> hata SAYILMAZ, sadece mevcut-ama-mock durumu kontrol edilir.

Test Technique: conftest.find_polluted_project_modules (saf fonksiyon)
izole test edilir (unit, %60). pytest_collection_finish hook'unun
GERÇEKTEN pytest sürecini durdurduğu, gerçek bir pytest alt-süreciyle
(subprocess) doğrulanır (integration, %40).
"""

import os
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest

sys.path.insert(0, os.getcwd())

from tests.conftest import find_polluted_project_modules, PROJECT_OWN_MODULE_PREFIXES


# ---------------- AC-1, AC-2, AC-4, AC-5: find_polluted_project_modules (pure) ----------------

class TestFindPollutedProjectModules:
    def test_no_pollution_returns_empty(self):
        """AC-1: hiçbir proje modülü mock değil -> boş liste."""
        fake_sys_modules = {
            "src.parsers.veri_cekici_ayristirici": object(),  # gerçek modül nesnesi (basitleştirilmiş)
            "text_gen_parser": object(),
            "google": MagicMock(),  # 3.parti, mock OLABİLİR, sorun değil
            "pymongo": MagicMock(),
        }
        assert find_polluted_project_modules(fake_sys_modules) == []

    def test_one_polluted_project_module_detected(self):
        """AC-2: bir proje modülü (src.*) MagicMock -> tespit edilir."""
        fake_sys_modules = {
            "src.parsers.veri_cekici_ayristirici": MagicMock(),
            "src.api.webhook_server": object(),
            "google": MagicMock(),
        }
        result = find_polluted_project_modules(fake_sys_modules)
        assert result == ["src.parsers.veri_cekici_ayristirici"]

    def test_plain_mock_instance_also_detected(self):
        """unittest.mock.Mock (MagicMock'un ebeveyni) de yakalanmalı, sadece MagicMock değil."""
        fake_sys_modules = {"vps_main": Mock()}
        assert find_polluted_project_modules(fake_sys_modules) == ["vps_main"]

    def test_multiple_polluted_modules_all_listed(self):
        """AC-4: birden fazla proje modülü kirli -> hepsi listelenir (ilkini bulup durmaz)."""
        fake_sys_modules = {
            "src.parsers.veri_cekici_ayristirici": MagicMock(),
            "src.utils.reporter": MagicMock(),
            "text_gen_parser": object(),
        }
        result = find_polluted_project_modules(fake_sys_modules)
        assert result == ["src.parsers.veri_cekici_ayristirici", "src.utils.reporter"]

    def test_module_not_present_at_all_not_flagged(self):
        """AC-5: proje modülü sys.modules'ta hiç yoksa (henüz import edilmemiş) hata SAYILMAZ."""
        fake_sys_modules = {"google": MagicMock()}  # text_gen_parser, vps_main, src.* hiç yok
        assert find_polluted_project_modules(fake_sys_modules) == []

    def test_third_party_mocks_never_flagged(self):
        """Kapsam Dışı: google/pymongo/dotenv/pyngrok gibi 3.parti mock'lar MEŞRU, hiç yakalanmaz."""
        fake_sys_modules = {
            "google": MagicMock(),
            "google.genai": MagicMock(),
            "pymongo": MagicMock(),
            "pymongo.errors": MagicMock(),
            "dotenv": MagicMock(),
            "pyngrok": MagicMock(),
        }
        assert find_polluted_project_modules(fake_sys_modules) == []

    def test_similarly_named_non_project_module_not_false_flagged(self):
        """'src' prefix kontrolü tam sınır kontrolü yapmalı — 'srclib' gibi alakasız bir
        modül adı 'src' ile başlıyor diye yanlışlıkla proje modülü SAYILMAMALI."""
        fake_sys_modules = {"srclib": MagicMock(), "vps_maintenance": MagicMock()}
        assert find_polluted_project_modules(fake_sys_modules) == []

    def test_exact_top_level_module_names_detected(self):
        """Kök dizin modülleri (text_gen_parser, vps_main, production_parser) tam isim
        eşleşmesiyle de yakalanmalı (alt-modül değil, kendisi)."""
        fake_sys_modules = {
            "text_gen_parser": MagicMock(),
            "vps_main": MagicMock(),
            "production_parser": MagicMock(),
        }
        result = find_polluted_project_modules(fake_sys_modules)
        assert result == ["production_parser", "text_gen_parser", "vps_main"]

    def test_project_own_module_prefixes_matches_real_project_structure(self):
        """Red-team bulgusu: statik bir küme ile karşılaştırma TAUTOLOJIKTİ
        (liste kendisiyle eşleşiyor, gerçek dosya sistemiyle değil — bu
        yüzden rthook_backports.py'nin listeye hiç girmediğini hiç
        yakalamamıştı). Artık GERÇEK kök dizin taranıp liste buna göre
        doğrulanıyor — yeni bir kök .py dosyası eklenip listeye
        (conftest.py'nin dinamik türetimine) yansımazsa bu test fail eder."""
        repo_root = Path(os.getcwd())
        real_top_level_modules = {p.stem for p in repo_root.glob("*.py")}
        assert real_top_level_modules.issubset(set(PROJECT_OWN_MODULE_PREFIXES)), (
            f"Kök dizindeki şu modüller PROJECT_OWN_MODULE_PREFIXES'te eksik: "
            f"{real_top_level_modules - set(PROJECT_OWN_MODULE_PREFIXES)}"
        )
        assert "src" in PROJECT_OWN_MODULE_PREFIXES


# ---------------- AC-2, AC-3: pytest_collection_finish integration (gerçek subprocess) ----------------

class TestCollectionFinishHookIntegration:
    def test_hook_stops_pytest_when_module_level_pollution_persists(self, tmp_path):
        """AC-2: bugünkü canlı olayın birebir simülasyonu — bir sahte test dosyası
        sys.modules['src.fake_module']'ü modül seviyesinde mock'layıp GERİ ALMAZ.
        Gerçek pytest alt-süreci bunu tespit edip başarısız (exit != 0) dönmeli."""
        conftest_src = (tmp_path / "conftest.py")
        real_conftest = os.path.join(os.getcwd(), "tests", "conftest.py")
        conftest_src.write_text(open(real_conftest, encoding="utf-8").read(), encoding="utf-8")

        polluting_test = tmp_path / "test_polluting.py"
        polluting_test.write_text(textwrap.dedent("""
            import sys
            from unittest.mock import MagicMock
            # Bugünkü canlı olayın birebir tekrarı: modül seviyesinde atama, HİÇ geri alınmıyor.
            sys.modules['src.fake_module_for_pollution_test'] = MagicMock()

            def test_dummy():
                assert True
        """), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", ".", "-q", "-p", "no:cacheprovider",
             "--rootdir", str(tmp_path), "--override-ini=addopts="],
            capture_output=True, text=True, timeout=30, cwd=str(tmp_path),
        )
        assert result.returncode != 0, (
            f"Kirlilik varken pytest BAŞARILI dönmemeli.\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        combined = result.stdout + result.stderr
        assert "src.fake_module_for_pollution_test" in combined, (
            f"Hata mesajı hangi modülün kirli olduğunu İSİMLENDİRMELİ.\nCombined: {combined}"
        )

    def test_hook_allows_clean_run_with_temporary_function_scoped_monkeypatch(self, tmp_path):
        """AC-3: fonksiyon içi monkeypatch.setitem (test bitince pytest tarafından
        OTOMATİK geri alınır) YANLIŞLIKLA kirlilik sayılmamalı — normal pytest çıkışı (0)."""
        conftest_src = (tmp_path / "conftest.py")
        real_conftest = os.path.join(os.getcwd(), "tests", "conftest.py")
        conftest_src.write_text(open(real_conftest, encoding="utf-8").read(), encoding="utf-8")

        clean_test = tmp_path / "test_temporary_monkeypatch.py"
        clean_test.write_text(textwrap.dedent("""
            import sys
            from unittest.mock import MagicMock

            def test_uses_temporary_monkeypatch(monkeypatch):
                # Gecici, fonksiyon-icyerinde -- test bitince pytest OTOMATIK geri alir.
                monkeypatch.setitem(sys.modules, 'src.fake_module_temporary', MagicMock())
                assert True
        """), encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "-m", "pytest", ".", "-q", "-p", "no:cacheprovider",
             "--rootdir", str(tmp_path), "--override-ini=addopts="],
            capture_output=True, text=True, timeout=30, cwd=str(tmp_path),
        )
        assert result.returncode == 0, (
            f"Gecici fonksiyon-ici monkeypatch YANLIS POZITIF uretmemeli.\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
