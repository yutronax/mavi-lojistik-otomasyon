# Verify Report — blacklist-normalize-fix
_Reference: atdd.md, plan.md, test_diff.md, code_diff.md_

## Verification Gates
| # | Gate | Result | Evidence / Reason |
|---|------|--------|--------------------|
| 1 | Dosya konumu | PASS | `git status --short` ile doğrulandı: `src/utils/phone_utils.py`, `src/services/data_service.py`, `src/gui/components/blacklist_tab.py` değişmiş (`M`), `tests/test_blacklist_normalize.py` yeni (`??`). |
| 2 | Build/derleme | PASS | `python -c "import src.utils.phone_utils"` (gerekli mock'larla) sorunsuz; `python -m pytest --collect-only -q` proje genelinde 213 test, hiçbir import/collection hatası yok. |
| 3 | Supabase şema/canlı doğrulama | N/A | Bu görev Supabase'e dokunmuyor — hiçbir migration dosyası veya `{supabase_url}/rest/v1/...` çağrısı değişmedi (proje zaten Supabase değil MongoDB kullanıyor). |
| 4 | Lint | N/A | Repoda `ruff`/`eslint`/`.flake8`/`pyproject.toml` lint config yok, `.github/workflows/ci.yml` da lint adımı çalıştırmıyor. |
| 5 | Type check | N/A | Repoda `pyright`/`mypy` yapılandırması yok, CI da type-check çalıştırmıyor. |
| 6 | Unit testler | PASS | CI'ın kendi komutu (`.github/workflows/ci.yml`: `pytest -q`) birebir çalıştırıldı: **213 passed, 1 warning in 98.50s** (proje genelinde, sadece yeni dosya değil). Ayrıca hedefli çalıştırma: `pytest tests/test_blacklist_normalize.py tests/test_blacklist_sender_number_field.py -q` → **30 passed in 0.13s**. |
| 7 | E2E testler | N/A | Proje Playwright/Cypress gibi bir e2e suite tanımlamıyor; bu görev Flet masaüstü GUI'sinde, rendered bir web sayfası değil. |
| 8 | Lighthouse (performans) | N/A | Web UI kapsamında değil (Flet masaüstü uygulaması). |
| 9 | Erişilebilirlik | N/A | Gate 8 ile aynı gerekçe. |
| 10 | Güvenlik taraması | INCONCLUSIVE | `security-scan` skill'i değişen 3 dosyaya karşı çalıştırıldı: `secrets` PASS, `python_sast` (bandit) PASS, `python_deps` (pip-audit) **TIMEOUT** (300s içinde bitmedi, ağ yavaşlığı), `node_deps` N/A (package.json yok). Runner kendi verdict'ini `INCONCLUSIVE` olarak işaretledi — PASS olarak raporlanmıyor. |
| 11 | AI code review | PENDING (red-team) | Ayrı `red-team` adımına bırakıldı, burada tekrarlanmadı. |
| 12 | Görsel regresyon | N/A | Rendered web UI kapsamında değil. |
| 13 | DAST (ZAP) | N/A | Web UI kapsamında değil, `threat-model` adımı bu görev için hiç çalıştırılmadı (AC-S<n> üretilmedi). |
| 14 | İnsan onayı | PENDING | Kullanıcı onayı bekleniyor — bu skill veya `red-team` onay veremez. |

## AC -> Test Mapping
1. AC-1 (normalize edilmiş kayıt) -> `test_add_blacklist_normalizes_and_saves_ac1`, `test_normalize_phone_with_spaces_ac1`, `test_normalize_phone_with_dashes_ac1`, `test_normalize_phone_with_plus_and_spaces_ac1`, `test_save_and_load_normalized_blacklist_ac1_ac3` -> PASS
2. AC-2 (is_phone_in_list normalize eşleşme + reason ayrı saklama) -> `test_is_phone_in_list_with_unnormalized_in_list_ac1_ac2`, `test_add_blacklist_with_reason_saves_separately_ac2` -> PASS
3. AC-3 (VPS regresyon) -> `test_is_phone_in_list_with_normalized_list_ac3`, `test_vps_existing_blacklist_still_matches_ac3`, `test_is_phone_in_list_returns_false_for_non_matching_ac3`, `test_save_and_load_normalized_blacklist_ac1_ac3`, + `tests/test_blacklist_sender_number_field.py` (6 test, ayrı dosya) -> PASS
4. AC-4 (duplicate tespiti) -> `test_normalize_produces_same_for_different_formats_ac4`, `test_add_blacklist_detects_duplicate_ac4` -> PASS
5. AC-5 (geçersiz numara reddi) -> `test_normalize_phone_invalid_too_short_ac5`, `test_normalize_phone_invalid_too_long_ac5`, `test_add_blacklist_rejects_invalid_short_phone_ac5`, `test_add_blacklist_rejects_invalid_long_phone_ac5`, `test_invalid_phone_too_short`, `test_invalid_phone_too_long`, `test_invalid_phone_empty_string` -> PASS
6. AC-6 (karışık string+dict coercion, crash yok) -> `test_is_phone_in_list_with_dict_entries_ac6`, `test_save_blacklist_with_dict_entries_no_crash_ac6`, `test_save_blacklist_coerces_to_normalized_strings_ac6` -> PASS

## Coverage / Quality Notes
- Davranış Sözleşmesi tablosunun satır 3 (kaynak yok/silme) ve satır 5 (Mongo sync hatası) için ayrı yeni test yazılmadı — atdd.md bu satırlar için "mevcut davranış korunur" demişti; kod incelemesinde (`code_diff.md`) bu davranışlara dokunulmadığı doğrulandı, ama bunlar için açık bir regresyon testi yok. Kritik değil (davranış değişmedi) ama not düşülüyor.
- `test_diff.md`'de belirtilen "20/24 test zaten baştan PASS'tı" gözlemi hâlâ geçerli — ideal test-first disiplini tüm AC'lerin implementasyon öncesi kırmızı olmasıydı, ancak 4 gerçek red test (AC-2 dict eşleşmesi, AC-5 iki uzunluk validasyonu) implementasyon sonrası doğru şekilde yeşile döndü, bu asıl regresyon riskini kapsıyor.
- Gate 10 (güvenlik) **INCONCLUSIVE** kaldı — `pip-audit` ağ zaman aşımına uğradı. Bu bir FAIL değil ama PASS da değil; commit öncesi tekrar denenmesi (daha uzun timeout veya farklı ağ koşulunda) önerilir, ancak bu görevin değiştirdiği 3 dosya yeni bir bağımlılık eklemiyor, risk düşük.
- Gate 14 (İnsan onayı) ve Gate 11 (red-team) hâlâ bekliyor — pipeline'ın sıradaki adımı.
