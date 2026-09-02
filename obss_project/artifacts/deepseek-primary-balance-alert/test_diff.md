# Test Diff — deepseek-primary-balance-alert
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_deepseek_primary_balance_alert.py` (14 test, senkron pytest).

## AC → Test eşleşmesi

| AC | Test | Durum (red step) |
|---|---|---|
| AC-1 (DeepSeek birincil model) | `TestDeepSeekModelOrder::test_stage1_model_order_deepseek_first`, `test_stage2_model_order_deepseek_first` | FAIL |
| AC-2 (periyodik bakiye kontrolü) | `TestDeepSeekBalancePeriodicCheck::test_deepseek_balance_thread_exists`, `test_deepseek_balance_cache_initialization` | FAIL |
| AC-2/3/4 (bakiye kontrol mantığı) | `TestDeepSeekBalanceCheck::*` (5 test: yeterli/düşük/unavailable/ağ-hatası/key-yok) | FAIL |
| AC-3 (`/api/status` alanı) | `TestStatusEndpointDeepSeekBalance::*` (2 test) | FAIL |
| AC-5 (Groq fallback korunuyor) | `TestDeepSeekFallbackBehavior::test_groq_fallback_when_deepseek_unavailable` | PASS (mevcut değişmeyen davranış) |
| AC-6 (API key yoksa hata yok) | `TestDeepSeekApiKeyHandling::test_no_error_when_deepseek_api_key_undefined` | FAIL |
| Entegrasyon | `TestDeepSeekBalanceIntegration::test_full_pipeline_deepseek_primary_with_balance_alert` | FAIL |

**Doğrulanmış sonuç:** `python -m pytest tests/test_deepseek_primary_balance_alert.py -v` → **13 failed, 1 passed** (bağımsız olarak çalıştırılıp teyit edildi).

## Düzeltme geçmişi (test-copilot dispatch'i sırasında)
İlk yazımda 2 ciddi sorun bulundu, bağımsız doğrulamayla yakalandı:
1. **Yanlış import** (`from src.ai import text_gen_parser` — böyle bir modül yok) dosyanın TAMAMEN collection hatasıyla çökmesine neden oluyordu (0 test toplanıyordu). Düzeltme: `import text_gen_parser` (gerçek modül proje kökünde).
2. **Sahte-yeşil `hasattr` korumaları**: Çoğu test `if hasattr(admin_panel, 'X'):` bloğu içine assertion'ları sarmıştı — implementasyon henüz yokken bu korumalar testin gövdesini hiç çalıştırmadan sessizce PASS etmesine yol açıyordu (bu oturumda daha önce yakalanan aynı false-green kalıbı). Tüm bu korumalar kaldırıldı, fonksiyonlar doğrudan çağrılacak şekilde düzeltildi — artık implementasyon yoksa `AttributeError` ile GERÇEKTEN FAIL oluyorlar.
Ayrıca sub-agent, `text_gen_parser.py`'nin modül seviyesinde `from google import genai` import ettiğini (bu venv'de `google-genai` paketi kurulu değil) fark edip `sys.modules['google']`/`google.genai` mock'u ekledi — bağımsız doğrulandı, gerekli ve meşru bir düzeltme (kapsam dışı değil).

## Sıradaki adım
`code-copilot` — bu testleri (`tests/test_deepseek_primary_balance_alert.py`)
yeşile çevirecek implementasyonu yazacak: `text_gen_parser.py`'de model
sırası değişikliği, `admin_panel.py`'de `_deepseek_balance_cache`/
`_check_deepseek_balance_once`/`_refresh_deepseek_balance` + `/api/status`
güncellemesi.
