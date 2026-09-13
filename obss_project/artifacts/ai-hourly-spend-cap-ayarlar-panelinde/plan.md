# Plan — ai-hourly-spend-cap-ayarlar-panelinde
_Reference: atdd.md_

Frontend-pipeline: tetikleyici yok (Görsel/UI kriteri minimal — generic `<label>/<input>` deseniyle otomatik render, özel bir tasarım/CSS değişikliği yok).

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | AC-1: `EDITABLE_ENV_KEYS` listesine (satır 67-78, şu an 10 anahtar) `"AI_HOURLY_SPEND_CAP_TRY"` eklenecek. AC-S1: `settings_save` route'una (satır 1137-1168) SADECE bu anahtar için minimal sayısal validasyon eklenecek — `updates` sözlüğü oluşturulduktan hemen sonra, `.env`'e yazmadan ÖNCE. | low |

## New Files
Yok.

## Dependencies
- `EDITABLE_ENV_KEYS` doğrulandı: şu an 10 anahtar (whapi/refresh_interval temizliğinden sonra), grep ile teyit edildi.
- Mevcut testlerde (`tests/test_admin_panel_settings_cleanup.py`) `AI_HOURLY_SPEND_CAP_TRY` hiç kullanılmıyor (grep ile doğrulandı) — çakışma/regresyon riski yok.
- `text_gen_parser.py:103`'teki `is_hourly_cap_exceeded()` DOKUNULMAYACAK — sadece `os.getenv('AI_HOURLY_SPEND_CAP_TRY', '9')` okuma noktası, bu görev onun yazma tarafını (admin panel) etkiliyor.
- Validasyon mantığı: `float(v)` dener, `ValueError` yakalarsa VEYA sonuç negatifse reddet. Yeni bir helper fonksiyon eklemeye gerek yok (CAVEMAN) — `settings_save` içinde 3-4 satırlık bir inline kontrol yeterli.

## Migration Required?
Hayır. `.env` şeması değişmiyor, sadece yeni bir anahtar (zaten var olan bir env değişkeni) allowlist'e ekleniyor.

## Risks
- (atdd.md'den taşındı) Validasyon sadece bu tek anahtara özel — genel bir şema değil, bilinen borç.
- Validasyon eklerken TÜM `updates` sözlüğünü mü yoksa sadece `AI_HOURLY_SPEND_CAP_TRY` anahtarını mı reddedeceği net olmalı: atdd.md Davranış Sözleşmesi "Kısmi başarı" satırı zaten karar vermiş — `AI_HOURLY_SPEND_CAP_TRY` geçersizse TÜM istek 400 ile reddedilir (kısmi yazma yok, basitlik için).

## Open Questions
Yok — atdd.md zaten somut, kod okuması (`EDITABLE_ENV_KEYS`'in güncel hali, mevcut testlerin bu anahtara dokunmadığı) plan aşamasında doğrulandı. Sonnet 5 alt-ajanına dispatch gerekmedi.
