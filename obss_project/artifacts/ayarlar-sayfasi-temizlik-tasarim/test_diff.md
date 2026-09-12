# Test Diff — ayarlar-sayfasi-temizlik-tasarim

## Oluşturulan Dosya
- `tests/test_settings_page_cleanup.py` (yeni, 18 test fonksiyonu, 6 sınıf)

## AC → Test Eşlemesi
| AC | Test sınıfı/fonksiyonları |
|---|---|
| AC-1 (ölü alanlar yok) | `TestAC1_DeadFieldsNotExist` — 4 test |
| AC-2 (config sadece LLM anahtarları + env set) | `TestAC2_ConfigDictOnlyLLMKeys` — 4 test |
| AC-3 (eski config anahtarları zararsız) | `TestAC3_BackwardCompatibilityOldConfig` — 3 test |
| AC-4 (boş alan kaydı) | `TestAC4_EmptyFieldValuesHandling` — 3 test |
| AC-5 (disk hatası → _show_error) | `TestAC5_ErrorHandlingDuringSave` — 3 test |
| Happy path (integration) | `TestIntegrationHappyPath` — 1 test |

## İlk Çalıştırma Durumu (red step)
18 test, 10 FAIL / 8 PASS — beklenen: AC-1 (whapi/refresh_interval hâlâ mevcut) ve AC-2 (config'te hâlâ eski anahtarlar var) testleri implementasyon temizlenmeden fail eder. AC-3/AC-5 zaten mevcut davranışla geçiyor (regresyon garantisi).

## Not
Test dosyası `sys.modules['flet']` stub'ını dosya sonunda `del` ile geri alıyor (3. parti bağımlılık, proje modülü değil — kural gereği zorunlu değil ama temiz bırakılmış).
