# Plan — baileys-pro-model-kaldir-ve-blacklist-lid-fix
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `text_gen_parser.py` | AC-1/AC-2: `self.fallback_models = ['deepseek-v4-pro']` (satır 77) → `[]`. `models_to_try = [self.model_robust] + self.fallback_models + ['openai/gpt-oss-20b']` (satır 463) — `fallback_models` boşaldığı için otomatik olarak `[flash, groq]` sırasına düşer, satır 463'ün kendisine dokunmaya gerek YOK (zaten `self.fallback_models`'i referans alıyor). Satır 77'deki yorum (`# DeepSeek fallback (flash başarısız olursa)`) de güncellenmeli (artık boş liste olduğu açıklanmalı). | low |
| `sidecar/bridge.js` | AC-3/AC-4/AC-5: `toWhapiShape()` (satır 82) — `const senderJid = msg.key.participant || (isGroup ? null : from);` satırı, `msg.key.participantAlt` varsa onu, yoksa mevcut `msg.key.participant`'ı kullanacak şekilde değiştirilecek: `const senderJid = msg.key.participantAlt || msg.key.participant || (isGroup ? null : from);`. `participantAlt` doğrulandı: `@whiskeysockets/baileys`'in `Types/Message.d.ts:21`'inde `participantAlt?: string` olarak resmi, opsiyonel bir alan. | low |

## New Files
Yok.

## Dependencies
- `is_phone_in_list()` ([src/utils/phone_utils.py:58](src/utils/phone_utils.py:58)) — `get_phone_variants()` ile çeşitli telefon formatlarını normalize ediyor, `@s.whatsapp.net` sonekli JID formatına özel bir işlem GEREKMİYOR (mevcut Whapi akışında da aynı formatta çalışıyordu) — bu fonksiyona DOKUNULMUYOR, sadece ona giden `sender_raw` değeri artık (varsa) gerçek numara olacak.
- `senderName` hesaplaması (bridge.js satır 83: `msg.pushName || senderJid?.split('@')[0] || 'Bilinmeyen'`) — `senderJid` değişkeninin kendisi değiştiği için bu satır otomatik olarak yeni değeri (participantAlt varsa onu) kullanacak, ayrıca değiştirilmesine gerek yok.

## Migration Required?
Hayır — hiçbir dosya schema/DB değişikliği içermiyor, düz kod değişikliği.

## Risks
- (atdd.md'den) `participantAlt` her mesaj tipinde garantili değil — bu
  plan sadece "varsa kullan" fallback'ini uyguluyor, %100 çözüm iddiası
  yok.
- **YENİ (plan adımında doğrulandı):** `participantAlt`'ın tip tanımı
  gerçek ve resmi (`Message.d.ts:21`), ama bu SADECE alanın kütüphane
  tarafından TANIMLANDIĞINI kanıtlıyor, HER mesajda dolu geleceğini
  KANITLAMIYOR — çalışma zamanı davranışı VPS'te canlı gözlemle
  doğrulanmalı (bu görev kapsamında VPS erişimi yok, sonraki bir oturumda
  pm2 loglarıyla teyit edilmesi önerilir).
- `fallback_models`'in satır 463'te zaten referans alınması sayesinde
  `models_to_try`'a AYRICA dokunmaya gerek olmaması, bu değişikliği çok
  düşük riskli yapıyor — tek satırlık bir liste değişikliği.

## Open Questions
Yok — atdd.md'nin Assumptions/Unknowns bölümündeki `participantAlt`'ın tip
tanımı bu adımda doğrulandı (gerçek, opsiyonel bir alan), kalan belirsizlik
(çalışma zamanı doluluk oranı) zaten atdd.md'de açık bir sınırlama olarak
kabul edilmişti — yeni bir soru olarak sorulmaya gerek yok.
