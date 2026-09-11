#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
tests/conftest.py

test-sys-modules-izolasyon-korumasi: sys.modules kirliligi tespiti.

Bugunku canli olay: tests/test_webhook_server_threading.py'de
sys.modules['src.parsers.veri_cekici_ayristirici'] modul seviyesinde bir
MagicMock ile degistirilip hic geri alinmamisti. Pytest tum test
dosyalarini collection asamasinda import ettigi icin bu, tum surecin
paylastigi sys.modules cache'ini kalici kirletti -- test_junk_message_filter.py
ve test_hourly_spend_cap.py (7 test) aylarca "Got: MagicMock" hatasiyla
fail etti, kok nedeni bulmak gunler surdu.

monkeypatch.setitem(sys.modules, ...) burada KULLANILAMAZ -- mevcut desen
(agir bagimliliklari collection zamaninda, modul seviyesinde mock'lamak)
zorunlu (gec import edilirse collection'in kendisi patlar), ama
monkeypatch SADECE fonksiyon/fixture icinde calisir. Bu yuzden cozum
"otomatik restore" degil "TESPIT": collection bitince sys.modules'taki
proje-kendi modullerinin gercek mi mock mu oldugunu kontrol edip,
kirlilik varsa pytest'i HEMEN ve ACIKCA durdurmak.
"""

import glob
import sys
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest


def _discover_project_own_module_prefixes():
    """Kok dizindeki TUM .py dosyalarini (dosya adi, .py haric) + bilinen
    paket koku 'src'i DINAMIK olarak turetir. Statik/hardcoded bir liste
    (ilk versiyonda oldugu gibi) kendisi de 'insana guvenme' hatasina acikti
    -- red-team incelemesi rthook_backports.py'nin listeye hic girmedigini
    buldu (canli kanit: bu hook'un onlemeye calistigi TAM sinif hata,
    kendi bakim listesinde olustu). Dinamik turetim bu riski ortadan kaldirir."""
    repo_root = Path(__file__).resolve().parent.parent
    top_level_modules = tuple(Path(p).stem for p in glob.glob(str(repo_root / "*.py")))
    return top_level_modules + ("src",)


PROJECT_OWN_MODULE_PREFIXES = _discover_project_own_module_prefixes()


def _is_project_own_module(name):
    """name tam olarak bir prefix'e esit mi (kok modul) ya da 'prefix.' ile
    mi basliyor (alt-modul) -- 'srclib' gibi alakasiz bir ad 'src' ile
    baslasa bile YANLISLIKLA eslesmemeli (tam sinir kontrolu)."""
    return any(name == prefix or name.startswith(prefix + ".") for prefix in PROJECT_OWN_MODULE_PREFIXES)


def find_polluted_project_modules(modules):
    """Saf fonksiyon: sys.modules benzeri bir sozluk alir, projenin kendi
    modullerinden hangilerinin gercek modul yerine bir MagicMock/Mock
    instance'i oldugunu (alfabetik siralanmis) liste olarak doner.
    3.parti kutuphane mock'lari (google, pymongo, dotenv, pyngrok) kapsam
    disi -- sadece PROJECT_OWN_MODULE_PREFIXES ile eslesenler kontrol edilir."""
    polluted = []
    for name, module in modules.items():
        if not _is_project_own_module(name):
            continue
        if isinstance(module, (MagicMock, Mock)):
            polluted.append(name)
    return sorted(polluted)


def pytest_collection_finish(session):
    """Collection tamamlaninca (hicbir test daha CALISMADAN once) bir kez
    calisir. Fonksiyon-ici gecici monkeypatch.setitem kullanimlari test
    CALISTIRMA sirasinda olur (bu hook'tan SONRA) ve pytest tarafindan
    otomatik geri alinir -- bu yuzden burada YANLISLIKLA yakalanmazlar."""
    polluted = find_polluted_project_modules(sys.modules)
    if polluted:
        modules_str = ", ".join(polluted)
        pytest.exit(
            f"KIRLENME TESPIT EDILDI: {modules_str} gercek modul degil, bir "
            f"MagicMock/Mock instance'i. Muhtemel neden: bir test dosyasinin "
            f"sys.modules['<modul>'] = MagicMock() atamasini geri almamasi "
            f"(modul seviyesinde, fonksiyon/fixture disinda yapilmis olabilir). "
            f"Kirleten dosyayi bulmak icin: tests/ altinda 'sys.modules[' arayin, "
            f"yukaridaki modul adiyla eslesen bir atama arayin ve geri "
            f"alindigindan (del sys.modules[...] veya monkeypatch.setitem) emin olun.",
            returncode=1,
        )
