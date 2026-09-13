# Test Diff — ai-hourly-spend-cap-ayarlar-panelinde

## Oluşturulan Dosya
- `tests/test_admin_panel_ai_spend_cap.py` (yeni, 13 test fonksiyonu, 6 sınıf)

## AC → Test Eşlemesi
| AC | Test sınıfı/fonksiyonları |
|---|---|
| AC-1 (GET editable listesinde AI_HOURLY_SPEND_CAP_TRY) | `TestSettingsGetAiSpendCap` — 1 test |
| AC-2 (POST geçerli değer kaydı: 15, 0, 9.5) | `TestSettingsSaveAiSpendCap` — 3 test |
| AC-S1 (geçersiz değer 400, .env'e yazılmaz) | `TestValidationAiSpendCap` — 3 test |
| Davranış Sözleşmesi (kısmi başarı → tüm istek reddedilir) | `TestPartialFailureAiSpendCap` — 1 test |
| AC-5 (diğer anahtarlar validasyonsuz kalır) | `TestRegressionAiSpendCap` — 3 test |
| Regresyon (auth) | `TestAuthenticationAiSpendCap` — 2 test |

## İlk Çalıştırma Durumu (red step) — orkestratör tarafından bağımsız doğrulandı
`python -m pytest tests/test_admin_panel_ai_spend_cap.py -v` → **5 failed, 8 passed**.
Fail edenler beklenen: `test_get_settings_includes_ai_hourly_spend_cap`, `test_post_settings_save_valid_ai_spend_cap`, `test_post_settings_save_valid_zero`, `test_post_settings_save_valid_float`, `test_post_settings_partial_failure_ai_cap_invalid_other_valid` — hepsi `AI_HOURLY_SPEND_CAP_TRY` henüz `EDITABLE_ENV_KEYS`'te olmadığı için. Pass edenler (AC-S1'in "geçersiz değer" testleri dahil) şu an "yok sayılıyor" (allowlist'te olmadığı için zaten yazılmıyor) durumundan tesadüfen geçiyor — code-copilot sonrası GERÇEK validasyonla geçmeye devam etmeleri gerekiyor, `verify` adımında tekrar dikkatle kontrol edilecek.
