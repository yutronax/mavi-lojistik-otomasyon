# Verify Report — kara-liste-gonderen-numara-tespiti
_Reference: atdd.md, code_diff.md, test_diff.md_

## Verification Gates
| # | Gate | Result | Evidence / Reason |
|---|------|--------|--------------------|
| 1 | Dosya konumu | PASS | `git status --short`/`git diff --stat`: 3 dosya değişti (`src/services/data_service.py`, `src/services/mongo_service.py`, `src/parsers/veri_cekici_ayristirici.py`), 2 yeni test dosyası (`tests/test_blacklist_sender_number_field.py`, `tests/test_orchestrator_missing_sender_warning.py`) — code_diff.md/test_diff.md'nin iddiasıyla birebir örtüşüyor |
| 2 | Build/derleme | PASS | Projede ayrı bir "build" adımı yok (Python script projesi, CI'da da yok). `ast.parse()` ile 3 değişen dosyanın syntax'i doğrulandı: "syntax OK". `mongo_service.py`'nin gerçek `import` denemesi bu ortamda `pymongo` kurulu olmadığı için başarısız oldu — bu ortam eksikliği, DEĞİŞİKLİĞİN kendisiyle ilgisiz (testler zaten pymongo'yu mock'luyor, gerçek pytest çalıştırması bu sorunu yaşamadı) |
| 3 | Supabase şema/canlı doğrulama | N/A | Bu proje Supabase kullanmıyor (MongoDB + yerel JSON), değişen dosyalarda Supabase çağrısı/migration yok |
| 4 | Lint | N/A | `.github/workflows/ci.yml` incelendi — CI sadece `pytest -q` çalıştırıyor, repo'da linter config (ruff/eslint/flake8) yok |
| 5 | Type check | N/A | CI'da veya repo'da type checker (pyright/mypy) yapılandırması yok |
| 6 | Unit testler | PASS | CI'ın gerçek komutu (`pytest -q`) tam proje kökünden çalıştırıldı: **166 passed, 1 warning in 96.31s** (1 uyarı bu görevle ilgisiz, önceden var olan bir `pytest.mark.asyncio` uyarısı). Görev-özel 13 test (`test_blacklist_sender_number_field.py` + `test_orchestrator_missing_sender_warning.py`) ayrıca izole çalıştırıldı: 13/13 PASS |
| 7 | E2E testler | N/A | Proje bir masaüstü/backend script'i, web UI/e2e suite yok; bu görev hiçbir UI dosyasına dokunmadı |
| 8 | Lighthouse (performans) | N/A | Web UI yok |
| 9 | Erişilebilirlik | N/A | Web UI yok |
| 10 | Güvenlik taraması | PASS | `security-scan` runner (`scan.py --files data_service.py mongo_service.py veri_cekici_ayristirici.py --json`), exit 0, verdict PASS: secrets PASS (0 bulgu), python_sast PASS (0 bulgu), python_deps PASS (0 bulgu), node_deps N/A (package.json yok) |
| 11 | AI code review | PENDING (red-team) | Sonraki adım |
| 12 | Görsel regresyon | N/A | Web UI yok |
| 13 | DAST (ZAP) | N/A | Web UI yok, threat-model AC-S üretilmedi |
| 14 | İnsan onayı | PENDING | Kullanıcı onayı bekleniyor |

## AC -> Test Mapping
| AC | Test | Sonuç |
|---|---|---|
| AC-1 | `test_data_service_filters_by_sender_number_ac1` | PASS |
| AC-1 (regresyon) | `test_data_service_does_not_filter_by_sender_name_ac1_regression` | PASS |
| AC-2 | `test_mongo_service_filters_by_sender_number_ac2` | PASS |
| AC-3 (regresyon) | `test_regresyon_blacklist_check_still_works_ac3` | PASS |
| AC-4 | `test_lid_format_sender_produces_warn_log_ac4` | PASS |
| AC-5 | `test_missing_sender_raw_produces_warn_log_ac5`, `test_sender_raw_empty_fail_open_behavior_ac5` | PASS |
| AC-6 | `test_sender_number_field_source_is_jid_ac6_info` | PASS |
| AC-7 (regresyon) | `test_normalization_regression_0_format_ac7`, `test_normalization_regression_lid_format_ac7` | PASS |

Tüm Acceptance Criteria en az bir testle kaplı. Regresyon suite'i (166 test,
tüm proje) yeşil — bu değişiklik başka hiçbir mevcut davranışı bozmadı.

## Coverage / Quality Notes
- Test piramidi görev ölçeğine göre ağır unit-odaklı (atdd.md'nin önerdiği
  70/25/5 ile tutarlı) — 13 testin çoğu unit, `test_mongo_service_...` ve
  `test_data_service_...` entegrasyon niteliğinde (gerçek fonksiyonu mock'lı
  bağımlılıklarla uçtan uca çağırıyor).
- Bazı testler (`test_code_inspection_...`, `test_add_to_processing_queue_method_exists`)
  statik kod-okuma tabanlı — davranış testi değil, varlık/desen kontrolü.
  Bu, atdd.md'nin kabul ettiği bir sınırlama (test-copilot adımında not
  edildi) ama ileride gerçek davranış testleriyle güçlendirilebilir.
- Kod tarafında yeni soyutlama/yardımcı fonksiyon yok (CAVEMAN uyumlu,
  code_diff.md'de doğrulandı).
