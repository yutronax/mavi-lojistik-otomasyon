---
task_slug: web-admin-panel-ayarlar-temizlik-tasarim
jira_id: null
saga_task_id: 380
threat_model: done
priority: medium
coverage_target: 80
performance_target: null
memory_target: null
test_strategy:
  unit: 55
  integration: 25
  e2e: 20
affected_modules:
  - src/api/admin_panel.py
---

# ATDD — web-admin-panel-ayarlar-temizlik-tasarim

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #380 (epic #35 "Codebase Cleanup").

## Persona
Tek admin/sahip — web admin paneline (Flask, tek sayfa, mobil öncelikli) telefonundan token ile giriş yapıp uzaktan yönetiyor. Çoklu kullanıcı/rol katmanı yok.

## Hedef (Neden)
Ayarlar sekmesi, kod tabanında hiç okunmayan `START_HOUR`/`END_HOUR` env anahtarlarını gösteriyor — bu, Flet masaüstü uygulamasında (ayarlar-sayfasi-temizlik-tasarim, tamamlandı) tespit edilen whapi/refresh_interval kalıntılarıyla aynı türden bir sorun. Admini yanıltan ölü ayarları kaldırmak ve aynı zamanda bölümün görsel tasarımını modernize etmek.

## User Story
As a admin (panel sahibi)
I want Ayarlar sekmesinde sadece gerçekten kullanılan ayarları, modern bir görünümle görmek
So that hangi ayarın işe yaradığını anlayabilir, kafası karışmaz

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given admin Ayarlar sekmesini açar, When `/api/settings` GET çağrılır, Then yanıttaki `editable` listesi ve `settings` sözlüğü `START_HOUR`/`END_HOUR` içermez — sadece kalan 10 anahtar (FETCH_HOURS_BACK, DUPLICATE_CHECK_HOURS, DEFAULT_UI_FILTER_MINUTES, WHATSAPP_POLL_INTERVAL, AUTO_SUBMIT, BATCH_SLEEP_TIME, LOOP_WAIT_TIME, DEEPSEEK_API_KEY, GROQ_API_KEY, GEMINI_API_KEY) döner.
2. [Critical] Given frontend `loadSet()` dinamik render yapıyor, When Ayarlar sekmesi DOM'a yazılır, Then `START_HOUR`/`END_HOUR` için hiçbir `<label>`/`<input>` üretilmez (ekstra HTML değişikliği gerekmez, `editable` listesinden otomatik düşer).
3. [High] Given admin kalan 10 ayardan birini değiştirip Kaydet'e basar, When `POST /api/settings` çalışır, Then değer `.env` dosyasına atomic write ile yazılır, `ok:true` döner (mevcut davranış, değişmiyor).
4. [High] Given `.env` dosyasında eski `START_HOUR`/`END_HOUR` satırları hâlâ varsa, When GET/POST `/api/settings` çalışır, Then bu satırlara dokunulmaz (silinmez/değiştirilmez) — sadece UI'dan ve API yanıtından kayboldular.
5. [Medium] Given SİSTEM AYARLARI/AI API ANAHTARLARI bölümlerinin görsel tasarımı gözden geçiriliyor, When Ayarlar sekmesi render edilir, Then kart/input/grup başlığı stili modernize edilir (bkz. "Tasarım Yönü") — ham env-key isimleri (`FETCH_HOURS_BACK` gibi) korunur, Türkçe çeviri eklenmez (kapsam dışı).
6. [High] **AC-S1 (threat-model)** — Given eski/stale bir istemci `POST /api/settings`'e `{"settings": {"START_HOUR": "99", "DEEPSEEK_API_KEY": "x"}}` gönderir (START_HOUR artık `EDITABLE_ENV_KEYS`'te yok), When `settings_save` çalışır, Then `START_HOUR` `.env`'e YAZILMAZ (satır hiç oluşmaz/değişmez), `DEEPSEEK_API_KEY` normal şekilde güncellenir — saldırgan/stale-client girdisiyle allowlist'in gerçekten sunucu tarafında uygulandığı doğrulanır.

## Threat Model
Çağrıldı — STRIDE-lite uygulandı (`src/api/admin_panel.py`, `/api/settings` GET/POST, ikisi de `@require_auth`). Sonuç: Spoofing/Repudiation/DoS/Elevation bu diff'e uymuyor (auth mekanizması, loglama, yetki modeli bu görevde değişmiyor, zaten mevcut ve yeterli). Tampering kategorisinden **AC-S1** çıktı — `EDITABLE_ENV_KEYS` allowlist'inin küçültülmesinin gerçekten sunucu tarafında (istemci/stale-client girdisine karşı) uygulandığını doğrulayan tek somut, test edilebilir kriter. Info disclosure: GET `/api/settings` zaten (bu görevden önce de) API anahtarlarını düz metin JSON olarak dönüyor — bu, bu görevin kapsamı dışında bir ön-var-olan tasarım kararı (kabul edilen risk, bkz. Risks).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (GET ayarları listele) | 200 + `{settings, editable}` (10 anahtar) | Yok | Ayarlar sekmesinde 10 alan | AC-1, AC-2 |
| 2 | Happy path (POST kaydet) | 200 + `{ok:true, restarted:bool}` | `.env` güncellenir | "Kaydedildi ✓" toast | AC-3 |
| 3 | Girdi geçersiz/eksik (`updates` boş) | 400 + `{error:"Güncellenecek ayar yok"}` | Yok | Hata toast'ı | (mevcut davranış, değişmiyor) |
| 4 | Kaynak yok (`.env` okunamıyor) | 500 + `{error: str(e)}` | Yok | Hata toast'ı | (mevcut davranış, değişmiyor) |
| 5 | Yetkisiz erişim (token yok/geçersiz) | 401 + `{error:"Yetkisiz"}` | Yok | Login ekranına döner | (mevcut `@require_auth`, değişmiyor) |
| 6 | Dış bağımlılık hatası (PM2 restart başarısız) | 200 + `{ok:true, restarted:false}` | `.env` yine de yazılmış olur | "Kaydedildi, restart HATA" toast'ı | (mevcut davranış, değişmiyor) |
| 7 | Zaman aşımı | Uygulanmıyor | — | — | Yerel dosya I/O + `.env` yazma, ağ çağrısı yok |
| 8 | Kısmi başarı | Uygulanmıyor | — | — | `_atomic_write` tek seferde tüm dosyayı yazıyor, kısmi yazma senaryosu yok |
| 9 | Hiçbir şey yapılamadı ama hata yok | Uygulanmıyor (zaten AC yok → 400 döner) | — | — | `updates` boşsa zaten 400 dönüyor (satır 3), sessiz başarı senaryosu kodda yok |
| 10 | Allowlist dışı anahtar gönderilir (AC-S1) | 200 + `{ok:true}` (diğer geçerli anahtarlar varsa) | `.env`'de sadece izinli anahtarlar değişir | "Kaydedildi ✓" (allowlist dışı anahtar sessizce filtrelenir, hata değil) | AC-S1 |

Kısmi başarı: Uygulanmıyor (bkz. tablo satır 8, `_atomic_write` atomik).
Hiçbir şey yapılamadı ama hata da yok: `updates` boşsa (hiç geçerli anahtar yoksa) zaten 400 dönüyor — sessiz başarı yok, bu görev bu davranışı değiştirmiyor.
Boş sonuç ↔ hata ayrımı: `.env` okunamazsa (gerçek hata) 500 + `error` alanı döner; `EDITABLE_ENV_KEYS`'te olup `.env`'de tanımsız bir anahtar varsa (boş sonuç) `settings` sözlüğünde o anahtar hiç yer almaz (KeyError değil, sessizce atlanır) — ikisi ayrı, karışmıyor.

## Test Strategy
Unit: 55% — `settings_get`/`settings_save` route'larının Flask `test_client()` ile testi (mevcut desen: `tests/test_admin_panel_message_id_xss.py`, `tests/test_webhook_shared_secret_auth.py`), `EDITABLE_ENV_KEYS` listesinin START_HOUR/END_HOUR içermediğinin doğrulanması.
Integration: 25% — GET sonrası POST döngüsü (kaydedilen değerin gerçekten `.env`'e yazılıp geri okunduğu), AC-S1'in uçtan uca doğrulanması (stale anahtar gönderilip `.env`'de oluşmadığının teyidi).
E2E: 20% — INDEX_HTML içindeki `loadSet()`/`saveSet()` JS için gerçek bir test altyapısı yok; görsel doğrulama (madde 5, Tasarım Yönü) manuel/ekran görüntüsü ile yapılacak (`vision-test` bu ortamda web sayfası için kullanılabilir — Flet'ten farklı olarak bu bir gerçek HTTP/HTML sayfası).

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: Yok
Memory: Yok
Görsel/UI kriteri: Ayarlar sekmesi START_HOUR/END_HOUR göstermez; "Tasarım Yönü" bölümündeki modernizasyon kriterleri karşılanır; bu kriter `verify` adımında ekran görüntüsü + mümkünse `vision-test` ile doğrulanmalı (web sayfası olduğu için Playwright kullanılabilir, Flet'teki gibi N/A değil).
Diğer ölçülebilir kriterler: `/api/settings` GET yanıtında `START_HOUR`/`END_HOUR` hiç geçmez (grep/JSON assertion ile doğrulanabilir).

## Tasarım Yönü ("tasarım kısmını da" — kullanıcı isteği)
Somut kapsam: **sadece görsel stil** modernizasyonu — ham env-key isimleri (`FETCH_HOURS_BACK` gibi) korunur, Türkçe çeviri/friendly-name eklenmez (Sonnet 5 low alt-ajanı gerekçesi: kullanıcı yeni bir i18n katmanı istemedi, önceki Flet görevinde de sadece görsel modernizasyon yapılmıştı — tutarlılık). Hedef:
- `loadSet()`'in ürettiği `<label>`/`<input>` çiftlerine daha net bir dikey ritim/boşluk.
- Input focus rengi ve kart görünümü (mevcut CSS değişkenleri `--mut` vb. kullanılarak) zenginleştirilir.
- "SİSTEM AYARLARI" / "AI API ANAHTARLARI" grup başlıkları görsel olarak daha belirgin hale getirilir (mevcut `font-weight:700` düz metin yerine, örn. ince bir ayraç çizgisi veya ikon).
- API anahtarı alanlarının mevcut password-mask/göz ikonu davranışı (satır 2070-2074) korunur, dokunulmaz.
- Değişiklikler sadece `src/api/admin_panel.py` içindeki `INDEX_HTML` string'inin CSS/`loadSet()` bölümünde kalır.

## Kapsam Dışı
- Yeni ayar eklemek
- `.env` şemasını/anahtar isimlerini değiştirmek
- Backend validasyon eklemek (boş alan, format kontrolü vb.)
- Auth mekanizmasını (`require_auth`, token sistemi) değiştirmek
- env-key isimlerini Türkçeleştirmek/friendly-name eklemek
- Admin panelinin Ayarlar dışındaki sekmelerini (mesajlar, loglar, kara liste vb.) değiştirmek
- GET `/api/settings`'in API anahtarlarını düz metin döndürme tasarımını değiştirmek (kabul edilen risk, bkz. Risks)

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py`: `EDITABLE_ENV_KEYS` listesi (satır 67-80), `INDEX_HTML` içindeki CSS + `loadSet()`/`saveSet()` JS bloğu (satır ~2057-2085 ve ilgili stil tanımları)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu makinede git reposunun kökünün proje klasörüyle aynı olup olmadığı teyit edilmedi. Sonraki adımlarda arama `src/`, `tests/`, `obss_project/` gibi proje-içi dizinlerle sınırlı tutulmalı.

## Rollback Beklentisi
`.env` dosyası zaten `_atomic_write` ile yazılıyor (mevcut altyapı, bu görev değiştirmiyor). Hata olursa git ile kod seviyesinde geri dönüş yeterli — ekstra rollback mekanizması gerekmiyor.

## Risks
- GET `/api/settings` API anahtarlarını (`DEEPSEEK_API_KEY`/`GROQ_API_KEY`/`GEMINI_API_KEY`) düz metin JSON olarak dönüyor (sadece `@require_auth` korumalı, tek admin token'ı bilen görebilir) — bu, bu görevden ÖNCE de var olan bir tasarım kararı, bu görev kapsamında düzeltilmiyor (kapsam dışı, ayrı bir görev gerektirir).
- Tasarım zenginleştirmesi sırasında admin panelinin diğer sekmeleriyle (mesajlar, loglar) görsel tutarlılığın kazara bozulma riski — sadece Ayarlar sekmesi/CSS bloğu değişiyor, global stil dokunulmuyor.

## Assumptions
- `START_HOUR`/`END_HOUR`'ın hiçbir yerde okunmadığı önceki Explore taramasıyla (grep, src/tools/sidecar) doğrulandı kabul edildi.
- `EDITABLE_ENV_KEYS`'ten bir anahtar çıkarmanın frontend'i otomatik güncellediği (dinamik render, ekstra HTML gerekmez) doğrulandı (kod okuması ile, `loadSet()` fonksiyonu `d.editable` listesini map'liyor).

## Unknowns
Yok — kullanıcı net yönlendirme verdi ("masaüstüyle işimiz yok, aynı görevi bunda uygula, tasarım kısmını da").

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü/persona → Tek admin/sahip, telefonundan (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
2. Ana hedef/neden → Ölü ayarları göstermemek, yeni ayar eklenmiyor (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
3. Happy path → Ayarlar sekmesi açılır, START_HOUR/END_HOUR yok, 10 ayar listelenir (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
4. Edge case 1 (eski .env satırları) → Dokunulmaz (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
5. Edge case 2 (boş alan) → Kapsam dışı, mevcut davranış korunur (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
6. Davranış sözleşmesi → Yukarıdaki tablo (Sonnet 5 low alt-ajanı tarafından yanıtlandı + threat-model AC-S1 eklendi)
7. Başarı ölçütü → START_HOUR/END_HOUR hiç görünmez, tasarım kriterleri karşılanır (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
8. Tasarım Yönü → Sadece görsel stil, ham key isimleri korunur, Türkçe çeviri yok (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. Kapsam dışı → Yeni ayar, şema değişikliği, validasyon, auth değişikliği, i18n, diğer sekmeler (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
10. Bağımlılıklar → admin_panel.py (EDITABLE_ENV_KEYS + INDEX_HTML CSS/JS) (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
11. Güvenlik/performans kısıtı → API anahtarı maskeleme korunmalı, .env satırlarına dokunulmaz (Sonnet 5 low alt-ajanı tarafından yanıtlandı + threat-model STRIDE-lite)
12. Rollback → Mevcut atomic_write yeterli, git seviyesinde geri dönüş (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
13. Kabul kriteri sahibi → Kullanıcı, ekran görüntüsü onayı (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
14. Test stratejisi → Unit 55/Integration 25/E2E 20 (Sonnet 5 low alt-ajanı tarafından yanıtlandı: backend ağırlıklı, gerçek Flask test_client() var)
15. Bilinen riskler/varsayımlar → Dinamik render doğrulandı, dev/prod senkron riski düşük (tek dosya) (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
