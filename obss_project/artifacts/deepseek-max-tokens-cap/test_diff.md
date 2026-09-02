# Test Diff — deepseek-max-tokens-cap
_Reference: atdd.md, plan.md_

## Oluşturulan Dosya
`tests/test_deepseek_max_tokens_cap.py` (10 test, `@pytest.mark.asyncio`,
`test_deepseek_cost_fix.py`'nin mock desenini takip ediyor).

## AC → Test eşleşmesi

| AC | Test | Durum (red step) |
|---|---|---|
| AC-1 (Stage 1, her iki model) | `TestStage1MaxTokensParameter::*` (2 test) | FAIL |
| AC-2 (Stage 2, her iki model) | `TestStage2MaxTokensParameter::*` (2 test) | FAIL |
| AC-3 (normal/büyük mesaj, cap tetiklenmez) | `TestNormalMessageNoCap::test_normal_message_does_not_trigger_cap` | FAIL (mock zinciri Stage1→Stage2 sırasını henüz varsaymıyor, implementasyon sonrası netleşecek) / `test_large_message_approaching_cap_but_not_triggered` | PASS (max_tokens'tan bağımsız, mevcut davranışın regresyon koruması) |
| AC-4 (kesilme → fallback + log) | `TestJsonTruncatedAtMaxTokens::*` (2 test) | FAIL |
| AC-5 (API reddi → mevcut fallback) | `TestMaxTokensApiRejection::test_max_tokens_parameter_rejected_triggers_fallback` | FAIL |
| Entegrasyon (4 çağrı noktasının tümü) | `TestAllMaxTokensCallsIncluded::test_all_four_api_calls_have_max_tokens` | FAIL |

**Doğrulanmış sonuç:** `python -m pytest tests/test_deepseek_max_tokens_cap.py -v` → **9 failed, 1 passed** (bağımsız olarak çalıştırılıp teyit edildi). Tüm 9 FAIL, `max_tokens not found in ... kwargs` veya çağrı sayısı beklentisi gibi genuine nedenlerle — sahte-yeşil/vacuous bir test bulunmadı.

## Sıradaki adım
`code-copilot` — bu testleri (`tests/test_deepseek_max_tokens_cap.py`)
yeşile çevirecek implementasyonu yazacak: `text_gen_parser.py`'deki 4 API
çağrı noktasına (`satır ~279, ~290, ~465, ~476`) `max_tokens=1500`
eklenmesi, ve Stage 2'de `finish_reason == 'length'` durumunda
`truncated_at_max_tokens` içeren bir log satırı eklenmesi.
