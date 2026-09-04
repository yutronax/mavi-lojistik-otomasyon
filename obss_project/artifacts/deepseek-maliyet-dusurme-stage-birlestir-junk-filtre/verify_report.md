# Verify Report — deepseek-maliyet-dusurme-stage-birlestir-junk-filtre
_Reference: atdd.md, code_diff.md_

## Verification Gates
| # | Gate | Result | Evidence / Reason |
|---|------|--------|--------------------|
| 1 | Dosya konumu | PASS | `git status --short` ile `text_gen_parser.py`, `src/parsers/veri_cekici_ayristirici.py` değişmiş, `tests/test_stage_merge_call_count.py`, `tests/test_junk_message_filter.py` yeni dosya olarak doğrulandı. |
| 2 | Build/derleme | N/A (ön-var-olan ortam kısıtı) | `python -c "import text_gen_parser"` bu yerel venv'de `ImportError: cannot import name 'genai' from 'google'` veriyor — bu, `google-genai` paketinin bu ortamda kurulu olmamasından kaynaklanıyor, BU GÖREVİN DEĞİŞİKLİĞİYLE İLGİSİZ (mevcut testler zaten bu paketi `sys.modules` stub'ıyla mock'luyor, gerçek projenin CI'ı da aynı şekilde çalışıyor olmalı). |
| 3 | Supabase şema/canlı doğrulama | N/A | Proje Supabase kullanmıyor (MongoDB/JSON dosya tabanlı) — bu görev hiçbir Supabase çağrısına/migrasyonuna dokunmuyor. |
| 4 | Lint | N/A | `.github/workflows/ci.yml` içinde lint/format adımı YOK, repo kökünde `ruff.toml`/`.flake8`/lint config dosyası yok — proje linter/formatter tanımlamıyor. |
| 5 | Type check | N/A | CI'da type-check adımı yok, `mypy.ini`/`pyrightconfig.json` yok. |
| 6 | Unit testler | **PASS (düzeltme sonrası)** | İlk turda 8 önceden var olan test FAIL vermişti (aşağıda detay). Kullanıcı onayıyla `test-copilot`'a geri dönülüp bu 8 test yeni tek-çağrı mimarisine göre güncellendi (7'si güncellendi, 1'i — artık test edilecek davranışı kalmayan `test_stage1_model_order_deepseek_first` — silindi, aynı dosyada zaten var olan `test_stage2_model_order_deepseek_first` ile duplike olmadığı doğrulandı). **Bağımsız olarak yeniden çalıştırıldı** (sub-agent özetine güvenilmedi): `python -m pytest -q` → **177 passed, 0 failed, 99.25s**. |
| 7 | E2E testler | N/A | Bu görevde rendered web UI yok, konfigüre edilmiş e2e suite yok. |
| 8 | Lighthouse | N/A | Web UI kapsamda değil. |
| 9 | Erişilebilirlik | N/A | Web UI kapsamda değil. |
| 10 | Güvenlik taraması | Çalıştırılmadı | Kod değişikliği düz mantık/prompt/regex — kritik güvenlik yüzeyi (auth, injection, secrets) içermiyor; `red-team` adımında ayrıca değerlendirilecek. |
| 11 | AI code review | PENDING (red-team) | Ertelendi, ayrı adım. |
| 12 | Görsel regresyon | N/A | Web UI kapsamda değil. |
| 13 | DAST (ZAP) | N/A | Web UI kapsamda değil, security AC yok. |
| 14 | İnsan onayı | PENDING | Kullanıcı onayı bekleniyor. |

## Gate 6 Detayı — KRİTİK BULGU

**CI'ın gerçek komutuyla** (`.github/workflows/ci.yml`: `pytest -q`, tüm
`tests/` dizini) tam suite çalıştırıldı:

```
8 failed, 170 passed, 1 warning in 90.81s
```

Bu görevin kendi yeni testleri (12/12) GEÇİYOR — ama **code-copilot'un
implementasyonu, ÖNCEDEN VAR OLAN 8 testi bozdu**. Bu testler eski (Stage 1
ayrı çağrıydı) mimariyi varsayıyordu — atdd.md'nin AC-1'i bu mimariyi
KASITLI olarak değiştirdiği için, bu testlerin artık **güncellenmesi**
gerekiyor (implementasyon hatası değil, test-copilot'un pre-existing test
güncellemesini atlamış olması):

```
FAILED tests/test_deepseek_max_tokens_cap.py::TestStage2MaxTokensParameter::test_stage2_deepseek_max_tokens_parameter_included
FAILED tests/test_deepseek_max_tokens_cap.py::TestStage2MaxTokensParameter::test_stage2_groq_max_tokens_parameter_included
FAILED tests/test_deepseek_max_tokens_cap.py::TestNormalMessageNoCap::test_normal_message_does_not_trigger_cap
FAILED tests/test_deepseek_max_tokens_cap.py::TestNormalMessageNoCap::test_large_message_approaching_cap_but_not_triggered
FAILED tests/test_deepseek_max_tokens_cap.py::TestJsonTruncatedAtMaxTokens::test_stage2_json_truncated_triggers_fallback_and_logs
FAILED tests/test_deepseek_max_tokens_cap.py::TestMaxTokensApiRejection::test_max_tokens_parameter_rejected_triggers_fallback
FAILED tests/test_deepseek_max_tokens_cap.py::TestAllMaxTokensCallsIncluded::test_all_four_api_calls_have_max_tokens
FAILED tests/test_deepseek_primary_balance_alert.py::TestDeepSeekModelOrder::test_stage1_model_order_deepseek_first
```

**Kök neden (her biri için):**
- `test_deepseek_max_tokens_cap.py`'deki 6 test, `parser.parse_async()`
  çağrıldığında **en az 2 API çağrısı** (Stage 1 + Stage 2) beklediği
  varsayımına dayanıyor (örn. `test_all_four_api_calls_have_max_tokens`,
  4 çağrı — Stage1 DeepSeek+Groq, Stage2 DeepSeek+Groq — bekliyor). Artık
  sadece Stage 2 çalıştığı için bu sayılar yanlış.
- `test_deepseek_primary_balance_alert.py::test_stage1_model_order_deepseek_first`
  `_extract_locations_stage1_async`'in kaynağını `inspect.getsource` ile
  okuyup `models_to_try = [...]` atamasını arıyor — code-copilot bu metodun
  gövdesini `return ""` stub'ına indirdiği için artık böyle bir atama yok.

**Bu bir regresyon mu, beklenen bir değişiklik mi?** Beklenen — AC-1
zaten "Stage 1 AYRI bir çağrı olarak ÇAĞRILMAMALI" diyor, yani "2 çağrı"
varsayan eski testler ARTIK YANLIŞ VARSAYIMLAR içeriyor. Ama bu testler
**silinmeden veya güncellenmeden** bırakılamaz — ya (a) yeni mimariye göre
güncellenmeli (1 çağrı bekleyecek şekilde), ya da (b) atdd.md'nin
"Kapsam Dışı" bölümüne bu testlerin bilerek modası geçmiş sayıldığı
açıkça yazılıp silinmeli. Bu KARAR kullanıcıya ait, verify bunu kendi
başına çözemez/silemez.

## AC -> Test Mapping
| AC | Test | Sonuç |
|---|---|---|
| AC-1 | `test_extract_locations_stage1_not_called`, `test_api_call_count_single_call_per_message` | PASS |
| AC-2 | `test_retry_chain_preserved_on_429_error` | PASS |
| AC-3 | `test_is_junk_message_function_exists`, `test_basic_junk_detection_no_city_no_keywords` | PASS |
| AC-4 | `test_non_junk_with_logistics_keyword_no_city`, `test_non_junk_with_phone_no_city`, `test_mixed_message_with_multiple_signals` | PASS |
| AC-5 | `test_regression_real_messages_no_false_positives` (450 gerçek mesaj) | PASS |
| AC-6 | `test_all_models_exhausted_behavior_unchanged` | PASS |
| (kapsam dışı ama etkilenen) | `test_deepseek_max_tokens_cap.py` (6 test), `test_deepseek_primary_balance_alert.py` (1 test) | **FAIL — güncelleme gerekiyor** |

## Coverage / Quality Notes
- Bu görevin KENDİ AC'leri tam kapsanıyor ve geçiyor.
- Ama tam test suite'i (CI'ın çalıştırdığı gerçek komut) regresyonsuz
  DEĞİL — 8 test artık kırık. **Bu görev "commit'e hazır" SAYILAMAZ**,
  önce bu 8 test ele alınmalı (test-copilot'a dönüp güncellenmeli veya
  kullanıcıyla birlikte bilinçli olarak kaldırılmalı).

## Sonraki Adım
Tüm mandatory gate'ler PASS/N/A. `red-team` — commit öncesi son bağımsız
inceleme.
