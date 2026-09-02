# Test Diff — baileys-pro-model-kaldir-ve-blacklist-lid-fix
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
| Dosya | Framework | Çalıştırma |
|---|---|---|
| `tests/test_pro_model_removed.py` | pytest | `python -m pytest tests/test_pro_model_removed.py -v` → **3 failed, 3 passed** (gerçek — pro model hâlâ `fallback_models`'te) |
| `sidecar/test_bridge_participant_alt.js` | Node builtin `assert` | `node sidecar/test_bridge_participant_alt.js` → **exit code 1** (gerçek — `toWhapiShape` henüz export edilmiyor) |

## Bağlayıcı Teknik Not (code-copilot için, plan.md'de açıkça yoktu)
`toWhapiShape` fonksiyonu AC-3/4/5'in test edilebilmesi için `bridge.js`'in
`module.exports`'una eklenmesi ZORUNLU — şu an sadece `writeQrState`,
`writeAuthenticatedState`, `writeGroupsState`, `buildGetMessage`,
`isDecryptFailedMessage` export ediliyor.

## AC → Test Eşlemesi
| AC | Davranış | Test Fonksiyonu | Dosya |
|---|---|---|---|
| AC-1 | flash başarısız → groq'a geçer, pro yok | `test_models_to_try_chain_without_pro` | Python |
| AC-2 | `fallback_models` boş, `deepseek-v4-pro` kod tabanında yok | `test_fallback_models_is_empty_list`, `test_no_pro_model_in_source_code` | Python |
| AC-3 | participantAlt dolu → `from` = participantAlt (LID değil) | `test_ac3_participantAlt_takes_priority` | JS |
| AC-4 | participantAlt yok → mevcut LID davranışı (regresyon yok) | `test_ac4_no_participantAlt_fallback_to_participant` | JS |
| AC-5 | senderName yeni senderJid'i kullanır | `test_ac5_senderName_uses_new_senderJid`, `test_ac5_pushName_takes_precedence` | JS |
| AC-6 | flash+groq ikisi de başarısız → mevcut davranış korunur (regresyon) | `test_parse_async_all_models_exhausted_behavior` | Python (şu an zaten PASS, implementasyon sonrası da PASS kalmalı) |

## Mevcut Durumda PASS Eden Testler (implementasyon öncesi, beklenen)
`test_parse_async_all_models_exhausted_behavior`, `test_parse_async_method_exists`,
`test_model_robust_is_flash` — bunlar regresyon/sanity testleri, pro model
kaldırılmadan önce de sonra da doğru olması gereken davranışları
doğruluyor (false-green DEĞİL, bilinçli regresyon koruması).

## code-copilot İçin Bağlayıcı Varsayımlar
- **`text_gen_parser.py`**: satır 77 `self.fallback_models = ['deepseek-v4-pro']` → `[]`. Satır 463'e (`models_to_try = [self.model_robust] + self.fallback_models + ['openai/gpt-oss-20b']`) DOKUNULMUYOR, otomatik olarak `[flash, groq]`'a düşüyor.
- **`sidecar/bridge.js`**: satır 82 `const senderJid = msg.key.participant || (isGroup ? null : from);` → `const senderJid = msg.key.participantAlt || msg.key.participant || (isGroup ? null : from);`. `toWhapiShape` `module.exports`'a eklenmeli.
