---
task_slug: panel-baileys-qr-gosterimi
jira_id: null
saga_task_id: 354
priority: high
coverage_target: 80
performance_target: "<500ms (QR endpoint yanıt süresi)"
memory_target: null
test_strategy:
  unit: 70
  integration: 20
  e2e: 10
affected_modules:
  - src/api/admin_panel.py
  - sidecar/bridge.js
  - data/ (yeni: qr paylaşım dosyası, örn. data/baileys_qr.json)
---

# ATDD — panel-baileys-qr-gosterimi

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (Saga task #354, epic #46 altında)

## Persona
Sistemin tek operatörü/sahibi (kullanıcının kendisi). Panel zaten `/api/login` ile korunuyor; bu görev için ek bir rol/yetki katmanı YOK — mevcut oturum yeterli.

## Hedef (Neden)
VPS'te headless çalışan Baileys sidecar (bridge.js) oturumu koparsa (401/loggedOut), yeniden bağlanmak için QR üretiyor ama bu QR sadece terminal/PM2 log çıktısına (ASCII, `qrcode-terminal` paketiyle) yazılıyor. Operatörün bunu okutmak için VPS'e SSH bağlanıp `pm2 logs` açması gerekiyor — pratik değil. Bu özellik QR'ı doğrudan tarayıcıdaki admin panelinde gösterip, operatörün telefonundan doğrudan oradan taramasını sağlar.

## User Story
As a sistem operatörü
I want Baileys oturumu koptuğunda üretilen QR kodu web admin panelinde görmek
So that VPS'e SSH bağlanmadan, doğrudan telefonumdan tarayarak oturumu yeniden açabileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given bridge.js `connection.update` event'inde yeni bir `qr` string'i aldı, When bu QR bir paylaşılan dosyaya (örn. `data/baileys_qr.json`, `{qr, generated_at}` şeklinde) yazılır, Then panel `/api/whatsapp/qr` endpoint'ine giriş yapmış (login) bir istemci istek attığında `200 OK` + `{"status": "need_auth", "qr": "data:image/png;base64,...", "generated_at": <epoch>}` döner.
2. [Critical] Given oturum zaten bağlı (bridge.js `connection.update`'te `connection: "open"` aldı), When panel `/api/whatsapp/qr` çağrılır, Then `200 OK` + `{"status": "authenticated", "qr": null}` döner ve panel QR bölümünü gizler.
3. [High] Given panel'e login OLMADAN `/api/whatsapp/qr` istek atılır, When mevcut oturum/token doğrulaması (admin_panel.py'nin var olan login mekanizması) başarısız olur, Then `401 Unauthorized` + `{"error": "login_required"}` döner (QR verisi ASLA login olmadan dönmez — güvenlik kısıtı).
4. [High] Given bridge.js PM2'de down/çökmüş (QR dosyası hiç üretilmemiş veya çok eski), When panel `/api/whatsapp/qr` çağrılır ve dosya yoksa, Then `202 Accepted` + `{"status": "waiting", "message": "QR henüz üretilmedi, bridge başlatılıyor olabilir"}` döner.
5. [Medium] Given panel açıkken QR süresi dolar (Baileys QR'ları ~20-60 sn'de yenilenir), When frontend periyodik polling (4 saniyede bir) yapıyorsa, Then bir sonraki polling'de dosyadaki güncel QR otomatik yansır — kullanıcı manuel yenileme yapmaz.
6. [Medium] Given bridge.js QR dosyasını yazarken panel aynı anda okuyor (race condition riski), When admin_panel.py dosyayı okur, Then bozuk/yarım JSON okuma hatası panel'i çökertmez — hata yutulup bir önceki geçerli QR (veya "waiting" durumu) döner.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (QR mevcut, login'li) | 200 + `{"status":"need_auth","qr":"data:image/png;base64,...","generated_at":<epoch>}` | yok (salt okuma) | Panelde QR görseli, "Telefonunuzdan WhatsApp > Bağlı Cihazlar'dan tarayın" | AC-1 |
| 2 | Girdi geçersiz / oturum zaten açık | 200 + `{"status":"authenticated","qr":null}` | yok | QR bölümü gizli, "WhatsApp Bağlı" rozeti | AC-2 |
| 3 | Kaynak yok (QR dosyası hiç üretilmemiş) | 202 + `{"status":"waiting","message":"..."}` | yok | "QR üretiliyor, lütfen bekleyin" mesajı, polling devam eder | AC-4 |
| 4 | Yetkisiz erişim (login yok) | 401 + `{"error":"login_required"}` | yok | Panel login ekranına yönlendirir | AC-3 |
| 5 | Dış bağımlılık hatası (bridge.js PM2'de down, QR dosyası çok eski — örn. >2dk) | 200 + `{"status":"waiting","message":"Bridge yanıt vermiyor olabilir, PM2 durumunu kontrol edin"}` | yok | Uyarı mesajı, "waiting" ile aynı görsel ama farklı metin | AC-4 (genişletilmiş) |
| 6 | Zaman aşımı (N/A — bu endpoint senkron dosya okuma, network call yok) | — | — | — | Silindi: dosya okuma <10ms sürer, timeout senaryosu anlamsız |
| 7 | **Kısmi başarı** (QR dosyası var ama JSON bozuk/parse hatası) | 200 + `{"status":"waiting","message":"QR okunamadı, yeniden üretiliyor"}` (hata yutulur, 500 DÖNMEZ) | yok | "waiting" ile aynı görünüm, panel çökmez | AC-6 |
| 8 | **Hiçbir şey yapılamadı ama hata yok** | N/A — bu senaryo bu özellik için anlamsız: her çağrı 4 durumdan birine (need_auth/authenticated/waiting/login_required) kesin olarak düşer, "sessiz hiçbir şey dönmeme" durumu yok | — | — | Silindi: state machine'de "hiçbir şey" diye bir dal yok |

Kısmi başarı: QR dosyası bozuksa (satır 7) hata 500 olarak dışa sızmaz, "waiting" durumuna düşürülür — panel her zaman 4 durumdan birini gösterir, asla ham exception/500 göstermez.
Hiçbir şey yapılamadı ama hata da yok: Uygulanamaz — yukarıda AC-4/satır 8'de gerekçelendirildi.
Boş sonuç ↔ hata ayrımı: "QR yok" (waiting, 202/200) ile "yetkin yok" (401) durum kodu ve `status` alanıyla net ayrılır — ikisi de asla aynı gövdeyi dönmez.

## Test Strategy
Unit: 70% — QR dosyası okuma/parse fonksiyonu (geçerli/bozuk/eksik dosya), durum mapping mantığı (need_auth/authenticated/waiting), auth kontrolü
Integration: 20% — `/api/whatsapp/qr` endpoint'i gerçek Flask test client ile (login'li/login'siz istek, dosya var/yok senaryoları), bridge.js'in QR dosyasına yazma fonksiyonu
E2E: 10% — panel açılıp QR görselinin gerçekten render olduğunu doğrulayan bir tarayıcı testi (mevcut `frontend-audit`/Playwright altyapısı varsa onunla, yoksa manuel doğrulama notu)

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: <500ms (dosya okuma + response, network call yok)
Memory: belirtilmedi (önemsiz boyutta bir özellik)
Görsel/UI kriteri: QR görseli panelde net okunabilir boyutta (min 200x200px) render olmalı, taranabilirlik gerçek bir telefonla test edilmeli (otomatik test bunu doğrulayamaz — manuel doğrulama gerekir, `verify` adımında not düşülsün)
Diğer ölçülebilir kriterler: polling aralığı 4 saniye (Haiku önerisi, kullanıcı onayı bekliyor — bkz. Assumptions)

## Kapsam Dışı
- Çoklu WhatsApp hesabı/numara desteği
- QR'ın SMS/e-posta ile gönderilmesi
- QR geçmişi/loglaması (sadece anlık son QR gösterilir)
- Rate limiting / DDoS koruması bu endpoint'e özel eklenmeyecek (mevcut panel-genel güvenlik neyse o geçerli)
- bridge.js'in kendisinin yeniden yazılması (sadece QR'ı dosyaya yazacak küçük bir ek yapılacak, event mantığı değişmeyecek)

## Etkilenen Dosyalar/Modüller (bilinen)
- `sidecar/bridge.js` — `connection.update` handler'ına (satır ~127-132 civarı) QR'ı `data/baileys_qr.json`'a yazma eklenir; `connection: "open"` geldiğinde dosyayı `{status: "authenticated"}` ile günceller/temizler
- `src/api/admin_panel.py` — yeni route `/api/whatsapp/qr` (mevcut `/api/whatsapp-health` route'unun yanına, satır ~755 civarı), mevcut login/auth deseni takip edilir
- Panel frontend (admin_panel.py içindeki `/` route'unun döndürdüğü HTML/JS, satır ~1836 civarı) — QR gösterme bölümü + polling JS eklenir
- Yeni dosya: `data/baileys_qr.json` (bridge.js yazar, admin_panel.py okur — iki ayrı PM2 process arası paylaşım)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — ancak önceki oturumlarda (bkz. pytest.ini düzeltmesi geçmişi) bu makinede git reposu kökünün proje klasörüyle örtüştüğü gözlemlendi. Yine de sonraki adımlar (`plan`, `code-copilot`, `test-copilot`) Grep/Glob çağrılarını `path` parametresiyle gerçek proje klasörüyle (`.claude/worktrees/festive-pare-2fb538`) sınırlamalı.

## Rollback Beklentisi
QR dosyası okunamazsa/bozuksa panel çökmez, "waiting" durumuna düşer (bkz. Davranış Sözleşmesi satır 7). bridge.js tarafında dosya yazma hatası olursa (disk dolu vb.) bridge.js'in ana WhatsApp bağlantı mantığı ETKİLENMEMELİ — QR dosyası yazma işlemi try/catch ile izole edilir, hata sadece log'a düşer.

## Risks
- İki ayrı PM2 process (bridge.js/Node ve admin_panel.py/Python) arasında dosya tabanlı paylaşım race condition'a açık — satır 6/7'deki "kısmi başarı" davranışıyla hafifletiliyor ama tam çözüm değil (bir sonraki QR polling'inde kendi kendine düzelir).
- QR görselinin taranabilirliği (boyut, kontrast) otomatik testle doğrulanamaz, manuel/gerçek telefon testi gerekir.

## Assumptions
- Polling aralığı 4 saniye olarak varsayıldı (Haiku alt-ajanı önerisi) — kullanıcı onayı bekliyor, farklı bir değer isterse `plan` adımından önce düzeltilebilir.
- QR paylaşım mekanizması olarak dosya tabanlı (`data/baileys_qr.json`) seçildi — VPS'te zaten `data/` klasörü PM2 process'leri arasında paylaşılan bir konum (deploy script'inde `--exclude="data"` ile korunuyor, yani kalıcı ve paylaşılan). Alternatif (HTTP ile bridge.js'e sorma) daha karmaşık olurdu, dosya bazlı yaklaşım mevcut proje deseniyle (JSON dosya tabanlı veri saklama, bkz. proje hafızası) tutarlı.
- QR görseli base64 PNG olarak üretilecek varsayıldı (`qrcode` npm paketi ile, mevcut `qrcode-terminal`'den farklı — `qrcode-terminal` sadece ASCII üretir, PNG için ek bir npm paketi gerekecek). Bu, `plan` adımında `package.json`'a yeni bağımlılık eklenmesi gerektiği anlamına gelir.

## Unknowns
- admin_panel.py'nin `/api/login` mekanizmasının tam şekli (session cookie mi, token mı) — `plan` adımında kod okunarak netleştirilecek, burada varsayım yapılmadı.

## Sorular ve Cevaplar (ham kayıt)
(Haiku alt-ajanı tarafından yanıtlandı — general-purpose agent, model: haiku)
1. Persona/auth → Tek operatör, mevcut login'in arkasında — admin_panel.py'de zaten `/api/login` route'u var.
2. Happy path mekanizması → bridge.js paylaşılan dosyaya (`data/baileys_qr.json`) yazar, admin_panel.py okur, base64 PNG olarak frontend'e döner, 4sn polling.
3. QR süre sonu → Polling ile otomatik yenilenir, kullanıcı manuel işlem yapmaz.
4. Oturum zaten açıkken → `{status: "authenticated", qr: null}`, panel bölümü gizler.
5-10. Davranış sözleşmesi satırları → yukarıdaki tabloya işlendi (200/202/401 kodlarıyla).
11. "Hiçbir şey yapılamadı ama hata yok" → Bu özellik için anlamsız, N/A olarak silindi.
12. Güvenlik/performans → QR login arkasında zorunlu, polling 4sn.
13. Test oranı → 70/20/10 (unit/integration/e2e) önerildi, kabul edildi.
14. Kapsam dışı → çoklu hesap, SMS/email gönderimi, QR geçmişi, özel rate limiting.
15. Rollback → panel çökmemeli, sadece QR bölümü etkilenmeli.
