# Test Diff — deepseek-cost-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_deepseek_cost_fix.py` (yeni `tests/` klasörü, pytest + `unittest.mock`, gerçek API çağrısı yok)

## AC → Test eşleşmesi

| AC | Test | Durum (red step) |
|---|---|---|
| AC-1 (Groq önce denenir) | `TestGroqPrimaryModel::test_parse_async_tries_groq_first` | FAIL |
| AC-2 (Groq hatası → DeepSeek) | `TestGroqAPIFailure::test_groq_api_error_triggers_deepseek_fallback` | FAIL |
| AC-3 (Groq boş sonuç → DeepSeek retry) | `TestGroqEmptyResultFallback::test_groq_empty_routes_triggers_deepseek` | FAIL |
| AC-4 (tümü başarısız → `[]`) | `TestAllModelsFail::test_all_models_fail_returns_empty_list` | FAIL |
| AC-5 (Groq 429 → DeepSeek) | `TestGroqRateLimit::test_groq_429_rate_limit_fallback` | FAIL |
| AC-6 (`provider` alanı, Groq) | `TestTrackSpendProvider::test_track_spend_provider_detection_groq` | FAIL |
| AC-6 (`provider` alanı, DeepSeek) | `TestTrackSpendProvider::test_track_spend_provider_detection_deepseek` | FAIL |
| AC-6c (sıfır token → yazma yok, mevcut davranış) | `TestTrackSpendProvider::test_track_spend_zero_tokens_no_write` | PASS (zaten doğru, korunuyor) |
| Happy path (Groq başarı, DeepSeek hiç çağrılmaz) | `TestHappyPath::test_happy_path_groq_success` | FAIL |

**Doğrulanmış sonuç:** `python -m pytest tests/test_deepseek_cost_fix.py -v` → **8 failed, 1 passed** (bağımsız olarak çalıştırılıp teyit edildi).

## Not
İlk yazımda 3 test (`test_groq_empty_routes_triggers_deepseek`, `test_groq_429_rate_limit_fallback`, `test_all_models_fail_returns_empty_list`) ve 2 test (`test_track_spend_provider_*`) gerçek assertion içermiyordu (yorum satırına alınmış veya anlamsız kontrol) — bu, implementasyon yapılmadan da hep yeşil kalacakları anlamına geliyordu. İkinci bir Haiku dispatch'i ile düzeltildi, `test_models_to_try_groq_first` (AC-1'i tekrar eden, değer kontrolü yapmayan test) silindi. Şimdiki hal bağımsız olarak doğrulandı.

## Sıradaki adım
`code-copilot` — bu testleri (`tests/test_deepseek_cost_fix.py`) yeşile çevirecek implementasyonu `plan.md`'nin "Files to Modify" listesine göre yazacak.
