# Test Diff — saatlik-harcama-ust-limit

## Oluşturulan Dosya
- `tests/test_hourly_spend_cap.py` (yeni, 10 test)

## Düzeltme Notu
İlk teslimde 2 entegrasyon testi (`test_ac2_ac3_integration_...`,
`test_ac1_integration_...`) var olmayan bir API'yi hedefliyordu
(`DataExtractorOrchestrator` diye bir sınıf yok — gerçek adı
`OrchestratorSDK`; `add_to_processing_queue()` tek dict değil liste
alıyor; `TextGenParser`/`WhatsAppAPI`/`GereksizMesajFiltresi` diye
import'lar gerçek kodda yok). Ayrıca bir test (`test_ac2_no_pro_model_in_
source_code`) `assert X or True` ile her zaman geçen anlamsız bir
tautolojiydi. İkinci bir Haiku dispatch'iyle: entegrasyon testleri gerçek
`OrchestratorSDK` API'sine göre düzeltildi (bağımlılıkları doğru
mock'lanarak), tautoloji test silindi, `datetime` patch hedefi
(`text_gen_parser.datetime`) düzeltildi.

Bağımsız doğrulama: `python -m pytest tests/test_hourly_spend_cap.py -v`
gerçekten çalıştırıldı — **10/10 doğru sebeple FAIL** (collection hatası
yok, hepsi "is_hourly_cap_exceeded fonksiyonu yok" tipi beklenen red).

## AC → Test Eşlemesi
| AC | Test Fonksiyonu | Beklenen (implementasyon öncesi) |
|---|---|---|
| AC-6 | `test_ac6_hourly_cap_exceeded_function_exists` | RED (fonksiyon yok) |
| AC-6 | `test_ac6_module_level_variables_exist` | RED (değişkenler yok) |
| AC-1 | `test_ac1_threshold_below_cap_returns_false` | RED |
| AC-6 | `test_ac6_exact_cap_limit_not_exceeded` | RED |
| AC-2 | `test_ac2_exceeds_cap_returns_true` | RED |
| AC-2 | `test_ac2_custom_cap_env_variable` | RED |
| AC-4 | `test_ac4_hour_change_resets_counter` | RED |
| AC-5 | `test_ac5_fail_open_missing_json_file` | RED |
| AC-2, AC-3 | `test_ac2_ac3_integration_add_to_processing_queue_blocks_new_message` | RED (gerçek OrchestratorSDK API'siyle) |
| AC-1 | `test_ac1_integration_add_to_processing_queue_allows_under_cap` | RED (gerçek OrchestratorSDK API'siyle) |

## Sonraki Adım
`code-copilot` — bu testleri geçirecek implementasyonu yazacak.
