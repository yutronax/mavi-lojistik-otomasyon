---
task_slug: ai-hourly-spend-cap-ayarlar-panelinde
jira_id: null
saga_task_id: 382
threat_model: done
priority: medium
coverage_target: 80
performance_target: null
memory_target: null
test_strategy:
  unit: 60
  integration: 30
  e2e: 0
affected_modules:
  - src/api/admin_panel.py
---

# ATDD — ai-hourly-spend-cap-ayarlar-panelinde

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #382 (epic #51 "AI Maliyet İzleme ve Doğruluğu").

## Persona
Tek admin/sahip — web admin paneline telefonundan giriş yapıp uzaktan yönetiyor.

## Hedef (Neden)
`AI_HOURLY_SPEND_CAP_TRY` env değişkeni zaten var ve gerçekten kullanılıyor (`text_gen_parser.py:103`, `is_hourly_cap_exceeded()`, varsayılan 9 TL) — saatlik AI API harcaması bu limiti aşarsa gelen mesajlar ertelenir. Ancak bu limit sadece `.env` dosyası elle düzenlenerek değiştirilebiliyor. Admin, AI harcamasını kod değiştirmeden/deploy gerektirmeden doğrudan panelden ayarlayabilmek istiyor.

## User Story
As a admin
I want AI saatlik harcama limitini (AI_HOURLY_SPEND_CAP_TRY) Ayarlar sekmesinden görüp değiştirmek
So that AI maliyetini kod değiştirmeden kontrol altında tutabilirim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given admin Ayarlar sekmesini açar, When `GET /api/settings` çağrılır, Then yanıttaki `editable` listesi `AI_HOURLY_SPEND_CAP_TRY`'ı içerir, mevcut değeri "SİSTEM AYARLARI" grubunda gösterilir (AI API ANAHTARLARI grubunda DEĞİL — maskelenmez, çünkü secret değil, üst limit).
2. [Critical] Given admin geçerli bir sayısal değer (örn. "15") girip "Kaydet + Restart"a basar, When `POST /api/settings` çalışır, Then `.env`'e `AI_HOURLY_SPEND_CAP_TRY=15` yazılır, `mavi-lojistik-server` PM2 üzerinden restart edilir, yeni limit `is_hourly_cap_exceeded()` tarafından etkin okunur.
3. [High] Given admin sadece "Kaydet" (restart olmadan) basar, When `.env` güncellenir ama process restart edilmez, Then yeni limit HEMEN etkili olmaz (mevcut genel davranış, bu görev değiştirmiyor — UI'daki mevcut uyarı metni zaten bunu kapsıyor).
4. [Critical] **AC-S1 (threat-model)** — Given `AI_HOURLY_SPEND_CAP_TRY` için geçersiz bir değer gönderilir (örn. "abc", boş string, negatif sayı), When `POST /api/settings` çalışır, Then istek 400 ile REDDEDİLİR, `.env`'e YAZILMAZ — geçersiz bir string `.env`'e yazılıp `is_hourly_cap_exceeded()`'ın `float()` çağrısını patlatıp fail-open (limit sessizce devre dışı) davranışını tetiklemesi önlenir.
5. [Medium] Given `AI_HOURLY_SPEND_CAP_TRY` dışındaki diğer `EDITABLE_ENV_KEYS` anahtarları (örn. `FETCH_HOURS_BACK`), When `POST /api/settings` çalışır, Then bu anahtarlar için mevcut "validasyonsuz" davranış DEĞİŞMEZ — yeni validasyon SADECE `AI_HOURLY_SPEND_CAP_TRY`'a özel.

## Threat Model
Çağrıldı — STRIDE-lite uygulandı (`src/api/admin_panel.py`, `/api/settings` POST, `@require_auth` korumalı, ama görevin kendisi validasyon boşluğuna odaklanıyor). Sonuç: Spoofing/Repudiation/Info Disclosure/DoS/Elevation bu diff'e uymuyor (auth mekanizması değişmiyor, secret değil). Tampering kategorisinden **AC-S1** çıktı — yetkili bir kullanıcı (veya yanlış tıklama) `AI_HOURLY_SPEND_CAP_TRY`'a geçersiz bir değer girerse, `is_hourly_cap_exceeded()`'ın fail-open tasarımı (hata → limit aşılmamış sayılır) yüzünden harcama limiti SESSİZCE devre dışı kalır — tam da bu görevin "harcamayı kontrol etmek" amacının tersi bir sonuç. Bu, somut ve test edilebilir tek güvenlik/doğruluk kriteri.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (geçerli sayı, kaydet+restart) | 200 + `{ok:true, restarted:true}` | `.env` güncellenir, PM2 restart | "Kaydedildi + Restart ✓" | AC-2 |
| 2 | Geçersiz sayısal girdi (AC-S1) | 400 + `{error: "..."}`| `.env`'e YAZILMAZ | Hata toast'ı | AC-S1 |
| 3 | Yetkisiz erişim | 401 (mevcut `@require_auth`) | Yok | Login ekranı | (değişmiyor) |
| 4 | Kaynak yok (`.env` okunamıyor) | 500 (mevcut davranış) | Yok | Hata toast'ı | (değişmiyor) |
| 5 | Dış bağımlılık hatası (PM2 restart başarısız) | 200 + `{ok:true, restarted:false}` (mevcut davranış) | `.env` yine de yazılmış olur | "Kaydedildi, restart HATA" | (değişmiyor) |
| 6 | Zaman aşımı | Uygulanmıyor | — | — | Yerel dosya I/O, ağ çağrısı yok |
| 7 | Kısmi başarı | Uygulanmıyor | — | — | `_atomic_write` atomik, `AI_HOURLY_SPEND_CAP_TRY` + diğer anahtarlar birlikte gönderilirse, geçersizse TÜMÜ reddedilir (kısmi kayıt yok — basitlik için, AC-S1'in kapsamı) |
| 8 | Hiçbir şey yapılamadı ama hata yok | Uygulanmıyor | — | — | `updates` boşsa zaten 400 dönüyor (mevcut davranış) |

Kısmi başarı: `AI_HOURLY_SPEND_CAP_TRY` geçersizse ve aynı istekte başka geçerli anahtarlar da varsa, TÜM istek 400 ile reddedilir (hiçbir anahtar yazılmaz) — kısmi yazma yapılmaz, basitlik ve öngörülebilirlik için (kullanıcı "bazıları kaydedildi bazıları edilmedi" karışıklığı yaşamaz).
Hiçbir şey yapılamadı ama hata da yok: `updates` boşsa zaten 400 dönüyor, bu görev değiştirmiyor.
Boş sonuç ↔ hata ayrımı: N/A — bu görev sadece POST tarafını (yazma) etkiliyor, GET tarafı değişmiyor.

## Test Strategy
Unit: 60% — validasyon fonksiyonunun sınır durumları (`"abc"`, `""`, `"-5"`, `"0"`, `"9.5"`, `None`) + `EDITABLE_ENV_KEYS`'in `AI_HOURLY_SPEND_CAP_TRY` içerdiğinin doğrulanması. Mevcut `tests/test_admin_panel_settings_cleanup.py` deseniyle aynı (Flask `test_client()`, `tmp_path` ile `.env` izolasyonu).
Integration: 30% — `POST /api/settings` ile gerçek geçerli/geçersiz değer gönderip `.env` dosyasının durumunu doğrulama (yazıldı/yazılmadı).
E2E: 0% — Manuel/görsel doğrulama kullanıcı tarafından yapılacak (Ayarlar sekmesinde alanı görüp değiştirebildiğini teyit).

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: Yok
Memory: Yok
Görsel/UI kriteri: `AI_HOURLY_SPEND_CAP_TRY` alanı "SİSTEM AYARLARI" grubunda (maskelenmeden) görünür; bu, `verify` adımında ekran görüntüsüyle doğrulanabilir (opsiyonel, küçük kapsam).
Diğer ölçülebilir kriterler: `GET /api/settings` yanıtında `AI_HOURLY_SPEND_CAP_TRY` editable listesinde geçer (grep/JSON assertion ile doğrulanabilir).

## Kapsam Dışı
- `is_hourly_cap_exceeded()`/`text_gen_parser.py`'nin iç mantığını değiştirmek.
- Yeni bir harcama limiti türü eklemek (örn. günlük limit).
- Diğer `EDITABLE_ENV_KEYS` anahtarlarına validasyon eklemek — sadece `AI_HOURLY_SPEND_CAP_TRY`'a özel, genel bir validasyon şeması kurulmuyor (bilinen borç, bkz. Assumptions).
- Frontend'de bu alana özel görsel öğe (TL sembolü, slider) — generic `<label>/<input>` deseniyle render edilecek.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py`: `EDITABLE_ENV_KEYS` listesi (satır 67-78), `settings_save` route'una (satır ~1137-1168) `AI_HOURLY_SPEND_CAP_TRY`'a özel minimal validasyon eklenecek.

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu makinede git reposunun kökünün proje klasörüyle aynı olup olmadığı teyit edilmedi. Sonraki adımlarda arama `src/`, `tests/`, `obss_project/` gibi proje-içi dizinlerle sınırlı tutulmalı.

## Rollback Beklentisi
`.env` zaten `_atomic_write` ile yazılıyor (değişmiyor). Hata olursa git ile kod seviyesinde geri dönüş yeterli.

## Risks
- Yeni eklenen validasyon, `AI_HOURLY_SPEND_CAP_TRY` için "her string kabul edilir" varsayan bir test yoksa risk düşük — mevcut testlerde bu anahtar hiç kullanılmıyor (grep ile doğrulanacak, plan adımında).
- Validasyon sadece bu tek anahtar için eklendiğinden, gelecekte benzer "davranışı etkileyen" başka bir env key eklenirse aynı desen tekrar elle uygulanmalı — bilinen borç, kapsam dışı bırakıldı.

## Assumptions
- Kullanıcının "para limiti" ifadesi `AI_HOURLY_SPEND_CAP_TRY`'a işaret ediyor kabul edildi (kullanıcı bu seçeneği `AskUserQuestion` ile onayladı: "Web admin panel — AI harcama limiti").
- Geçersiz değer için 400 dönmesi (sub-agent kararı) — kullanıcı henüz bunu doğrudan onaylamadı, Hard Stop'ta onaylanacak.

## Unknowns
Yok.

## Sorular ve Cevaplar (ham kayıt)
1. Persona → Tek admin/sahip (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
2. Ana hedef → Kod değiştirmeden AI harcamasını kontrol etmek (kullanıcı mesajından + Sonnet 5 low alt-ajanı)
3. Happy path → Kaydet+Restart, yeni limit hemen aktif (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
4. Edge case 1 (sadece Kaydet) → Restart olmadan yeni limit etkili olmaz, mevcut davranış (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
5. Edge case 2 (geçersiz değer) → Validasyon eklenmeli, 400 dönmeli (Sonnet 5 low alt-ajanı tarafından yanıtlandı: fail-open riski doğrudan görevin amacını baltalıyor) → AC-S1'e dönüştü
6. Davranış sözleşmesi → Yukarıdaki tablo (Sonnet 5 low alt-ajanı tarafından yanıtlandı + threat-model)
7. Başarı ölçütü → editable listesinde görünür, iç mantık değişmez (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → İç mantık, yeni limit türü, diğer anahtarlara validasyon, özel UI öğesi (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → admin_panel.py (EDITABLE_ENV_KEYS + settings_save) (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
10. Güvenlik/performans kısıtı → Secret değil, maskeleme gerekmez, Sistem Ayarları grubunda (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
11. Rollback → Mevcut atomic_write yeterli (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
12. Kabul kriteri sahibi → Kullanıcı (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
13. Test stratejisi → Unit 60/Integration 30/E2E 0 (Sonnet 5 low alt-ajanı tarafından yanıtlandı, +10% pay AC-S1 validasyon testleri için ayrıldı)
14. Bilinen riskler → Restart gerekliliği mevcut davranış, validasyon borç olarak sadece bu anahtara özel bırakıldı (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
