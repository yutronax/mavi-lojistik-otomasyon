# Test Diff — kara-liste-gonderen-numara-tespiti (red step)

## Oluşturulan Dosyalar
- `tests/test_blacklist_sender_number_field.py`
- `tests/test_orchestrator_missing_sender_warning.py`

## AC → Test eşleştirmesi
| AC | Test | Durum (implementasyon öncesi) |
|---|---|---|
| AC-1 | `test_data_service_filters_by_sender_number_ac1` | RED (AssertionError, bug kanıtlandı) |
| AC-1 | `test_data_service_does_not_filter_by_sender_name_ac1_regression` | PASS (bilgilendirici, bug'ı belgeliyor) |
| AC-2 | `test_mongo_service_filters_by_sender_number_ac2` | RED (AssertionError, aynı bug) |
| AC-3 | `test_regresyon_blacklist_check_still_works_ac3` | PASS (regresyon, mevcut davranış korunuyor) |
| AC-4 | `test_lid_format_sender_produces_warn_log_ac4` | RED (WARN log yok) |
| AC-5 | `test_missing_sender_raw_produces_warn_log_ac5` | PASS (statik kontrol — not: gerçek implementasyon sonrası tekrar doğrulanmalı) |
| AC-5 | `test_sender_raw_empty_fail_open_behavior_ac5` | PASS (fail-open regresyonu) |
| AC-6 | `test_sender_number_field_source_is_jid_ac6_info` | PASS (bilgilendirici, plan.md doğrulaması) |
| AC-7 | `test_normalization_regression_0_format_ac7` | PASS (regresyon) |
| AC-7 | `test_normalization_regression_lid_format_ac7` | PASS (regresyon) |

## Bilinen sınırlama
`test_missing_sender_raw_produces_warn_log_ac5` şu an kod-içi anahtar kelime
taramasıyla (statik) PASS veriyor çünkü mevcut kodda `logger.warning` ve
`sender_raw` zaten başka amaçlarla bir arada geçiyor olabilir — code-copilot
implementasyonu bittikten sonra `verify` adımında bu testin GERÇEKTEN yeni
eklenen WARN log'u mu tespit ettiği yeniden gözden geçirilmeli.

## Red durumu (implementasyon öncesi, doğrulandı)
```
3 failed (AC-1, AC-2, AC-4), 10 passed
```
