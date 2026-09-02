---
task_slug: panel-baileys-oturum-kapat
jira_id: null
saga_task_id: 356
priority: medium
coverage_target: 80
performance_target: "<3s (dosya silme + pm2 restart senkron çalışır)"
memory_target: null
test_strategy:
  unit: 60
  integration: 25
  e2e: 15
affected_modules:
  - src/api/admin_panel.py
---

# ATDD — panel-baileys-oturum-kapat

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (Saga task #356, epic #46 altında)

## Persona
Sistemin tek operatörü/sahibi (kullanıcının kendisi) — panel-baileys-qr-gosterimi görevindeki (Saga #354) aynı persona.

## Hedef (Neden)
Baileys WhatsApp oturumunu (örn. yanlış numara bağlandıysa, ya da bağlantı bozulduysa sıfırdan başlamak için) kesmek şu an VPS'e SSH bağlanıp `sidecar/auth_info_baileys/` klasörünü silip `pm2 restart mavi-baileys-bridge` çalıştırmayı gerektiriyor. Operatör bunu panelden tek tıkla yapabilmek istiyor.

## User Story
As a sistem operatörü
I want admin panelinde bir butonla WhatsApp (Baileys) oturumunu kesebilmek
So that VPS'e SSH bağlanmadan, yanlış/bozuk bir bağlantıyı sıfırlayıp yeniden QR taratabileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given panele login'li bir operatör, When "Bağlantıyı Kes" butonuna tıklayıp onay dialogunu onaylar, Then `POST /api/whatsapp/disconnect` çağrılır, `auth_info_baileys/` silinir, `pm2 restart mavi-baileys-bridge` çalıştırılır, `200 + {"success": true, "status": "logged_out"}` döner ve panel QR bekleme durumuna geçer.
2. [High] Given `auth_info_baileys/` zaten yok (oturum zaten kopuk), When endpoint çağrılır, Then idempotent olarak `200 + {"success": true, "status": "already_logged_out"}` döner (hata değil).
3. [High] Given login olmadan `/api/whatsapp/disconnect` çağrılır, When mevcut `require_auth` doğrulaması başarısız olur, Then `401 + {"error": "Yetkisiz"}` döner (mevcut dekoratör metniyle birebir aynı).
4. [High] Given dosya silme İZİN hatasıyla başarısız olur, When endpoint çağrılır, Then `500 + {"success": false, "error": "...", "step": "file_delete"}` döner, pm2 restart HİÇ denenmez.
5. [Medium] Given dosya silindi ama `pm2 restart mavi-baileys-bridge` başarısız olur (kısmi başarı), When endpoint tamamlanır, Then `500 + {"success": false, "error": "...", "step": "pm2_restart", "file_deleted": true}` döner — hangi adımın başarısız olduğu açıkça belirtilir.
6. [Medium] Given panelde buton, When tıklanır, Then bir JS `confirm()` onay dialogu ("Emin misiniz? WhatsApp bağlantısı kesilecek") ÖNCE gösterilir, onaylanmazsa hiçbir istek atılmaz.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path | `200 + {"success":true,"status":"logged_out"}` | `auth_info_baileys/` silinir, bridge restart olur | Confirm sonrası "Oturum kapatıldı" mesajı, QR bölümü "waiting" durumuna döner | AC-1 |
| 2 | Zaten kopuk (idempotent) | `200 + {"success":true,"status":"already_logged_out"}` | Sadece pm2 restart denenir (dosya zaten yok) | "Oturum zaten kapalıydı" mesajı | AC-2 |
| 3 | Yetkisiz erişim | `401 + {"error":"Yetkisiz"}` | yok | Panel login ekranına yönlendirir | AC-3 |
| 4 | Dosya silme başarısız (izin hatası) | `500 + {"success":false,"error":"...","step":"file_delete"}` | yok (pm2 restart denenmez) | Hata mesajı, "manuel müdahale gerekebilir" uyarısı | AC-4 |
| 5 | **Kısmi başarı** (dosya silindi, pm2 restart başarısız) | `500 + {"success":false,"error":"...","step":"pm2_restart","file_deleted":true}` | Dosya silinmiş durumda kalır | Hata mesajı + "dosya silindi ama servis restart olmadı, PM2'yi kontrol edin" | AC-5 |
| 6 | **Hiçbir şey yapılamadı ama hata yok** | N/A — her çağrı ya `success:true` (logged_out/already_logged_out) ya `success:false` (adım bilgisiyle) döner, üçüncü bir "sessiz" dal yok | — | — | Silindi: state machine'de "hiçbir şey" diye bir dal yok |

Kısmi başarı: Dosya silinip pm2 restart başarısız olursa `file_deleted: true` alanıyla açıkça işaretlenir — sonraki bir "tekrar dene" çağrısı `already_logged_out` dalına düşüp sadece pm2 restart'ı tekrar dener (dosya zaten yok).
Hiçbir şey yapılamadı ama hata da yok: Uygulanamaz — her çağrı ya `success:true` ya `success:false` (adım bilgisiyle) döner.
Boş sonuç ↔ hata ayrımı: "zaten kopuk" (`success:true, already_logged_out`) ile "silme/restart hatası" (`success:false`) `success` alanı ve `step`/`status` alanlarıyla net ayrılır.

## Test Strategy
Unit: 60% — `_pm2()` çağrısı mock'lanarak restart başarı/başarısızlık senaryoları, dosya silme (`shutil.rmtree` veya benzeri) mock'lanarak izin hatası senaryosu, idempotent "zaten yok" kontrolü
Integration: 25% — `/api/whatsapp/disconnect` endpoint'i gerçek Flask test client ile (login'li/login'siz, geçici bir `auth_info_baileys/` test klasörü oluşturup silinmesini doğrulama)
E2E: 15% — panelde buton tıklama → confirm dialog → response sonrası UI güncellemesi (Playwright ile, mevcut panel-baileys-qr-gosterimi görevindeki `verify` adımının aynı yöntemi)

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: <3s (dosya silme + pm2 restart senkron, network call yok)
Memory: belirtilmedi
Görsel/UI kriteri: confirm dialog gerçekten tetikleniyor mu, buton tıklandığında yanlışlıkla ikinci bir istek atılmıyor mu (double-click koruması) — `verify` adımında canlı tarayıcıyla doğrulanmalı (panel-baileys-qr-gosterimi'nin `verify` adımında bir CSS/JS hatası canlı testte yakalanmıştı, aynı titizlik burada da gerekli)
Diğer ölçülebilir kriterler: yok

## Kapsam Dışı
- Otomatik yeniden bağlanma (kesildikten sonra sadece yeni QR bekler, kendiliğinden tekrar bağlanmaz)
- Başka WhatsApp numarası ekleme/çoklu hesap desteği
- Oturum geçmişi/audit log (auth_info_baileys/ silinince geçmiş bilgi kaybolur, bu kabul edilebilir)
- `auth_info_baileys/` yedekleme/export özelliği
- Panel dışı (örn. Telegram bildirimi) bir onay/uyarı mekanizması

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` — yeni route `/api/whatsapp/disconnect` (POST, `@require_auth`), mevcut `_pm2(args)` yardımcı fonksiyonunu kullanır (satır ~132 civarı, `/api/service/<action>` route'unun deseni takip edilir)
- Panel frontend (`INDEX_HTML` sabiti) — "Bağlantıyı Kes" butonu + confirm dialog + sonuç mesajı, mevcut `baileys-qr-section` bölümünün yanına eklenir
- Sunucu tarafında `sidecar/auth_info_baileys/` klasörü silinir (kod değişikliği değil, çalışma zamanı etkisi)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — önceki görevlerde (panel-baileys-qr-gosterimi) bu makinede git reposu kökünün proje klasörüyle örtüştüğü gözlemlendi. Yine de sonraki adımlar Grep/Glob çağrılarını gerçek proje klasörüyle (`.claude/worktrees/festive-pare-2fb538`) sınırlamalı.

## Rollback Beklentisi
Dosya silme başarısız olursa pm2 restart hiç denenmez (sıralı, "step" bilgisiyle net hata döner) — sistem öncekiyle aynı (tutarlı) durumda kalır. Dosya silinip pm2 restart başarısız olursa (kısmi başarı), sistem "dosya yok ama eski process hâlâ çalışıyor" durumunda kalabilir — bu durumda bir SONRAKİ çağrı `already_logged_out` dalına düşüp sadece pm2 restart'ı tekrar dener, kendi kendine düzelme mekanizması budur (ayrı bir "retry" endpoint'i icat edilmedi, aynı endpoint'in tekrar çağrılması yeterli).

## Risks
- `pm2 restart mavi-baileys-bridge` komutu, bridge process PM2'de hiç kayıtlı değilse (örn. daha önce `pm2 delete` edilmişse) başarısız olur — bu durumda kullanıcıya "PM2'de servis bulunamadı, manuel `pm2 start` gerekebilir" gibi net bir hata mesajı gösterilmeli, sessizce yutulmamalı.
- Confirm dialog sadece frontend'de (JS `confirm()`) — teknik olarak bypass edilebilir (doğrudan API çağrısıyla), ama bu panel zaten login korumalı tek-operatör bir araç, ek bir backend-seviyesi "çift onay" mekanizması bu görevin kapsamında değil (Kapsam Dışı'na eklenebilirdi ama zaten AC'lerde yok).

## Assumptions
- Endpoint yolu `/api/whatsapp/disconnect` olarak varsayıldı (mevcut `/api/whatsapp/qr` ve `/api/whatsapp-health` route isimlendirme deseniyle tutarlı) — kullanıcı onayı bekliyor.
- Confirm dialog için basit JS `confirm()` yeterli varsayıldı (mevcut panelde `deleteMsg()` fonksiyonunun `confirm(...)` kullandığı gözlemlendi — panel-baileys-qr-gosterimi görevinden hatırlanan bir desen, bu görevde `plan` adımında kod okunarak doğrulanacak).
- Test oranı 60/25/15 (Haiku önerisi) — kullanıcı onayı bekliyor.

## Unknowns
- `_pm2()` yardımcı fonksiyonunun tam imzası ve dosya silme için projede kullanılan mevcut bir yardımcı (varsa) — `plan` adımında kod okunarak netleşecek.

## Sorular ve Cevaplar (ham kayıt)
(Haiku alt-ajanı tarafından yanıtlandı — general-purpose agent, model: haiku)
1. Persona/yetki → Confirm dialog zorunlu, geri dönüşsüz bir işlem olduğu için.
2. Happy path → tıkla → confirm → dosya sil → pm2 restart → panel "kapatıldı" mesajı.
3. Klasör zaten yoksa → idempotent, `already_logged_out` ile başarılı say.
4. PM2 restart başarısız → hata dön, kritik.
5-10. Davranış sözleşmesi satırları → yukarıdaki tabloya işlendi.
11. POST mu → Evet, GET ile yanlışlıkla tetiklenmeyi önlemek için, mevcut `/api/service/<action>` deseniyle tutarlı.
12. Test oranı → 60/25/15 (unit/integration/e2e) önerildi.
13. Kapsam dışı → otomatik yeniden bağlanma, çoklu hesap, audit log, yedekleme.
14. Rollback → kısmi başarı durumunda "step" bilgisiyle net hata, sonraki çağrı kendi kendine düzeltir.
