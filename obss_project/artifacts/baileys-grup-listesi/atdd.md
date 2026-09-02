---
task_slug: baileys-grup-listesi
jira_id: null
saga_task_id: 358
priority: medium
coverage_target: 80
performance_target: "<500ms (endpoint yanıtı, salt dosya okuma)"
memory_target: null
test_strategy:
  unit: 70
  integration: 20
  e2e: 10
affected_modules:
  - sidecar/bridge.js
  - src/api/admin_panel.py
---

# ATDD — baileys-grup-listesi

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (Saga task #358, epic #46 altında)

## Persona
Sistemin tek operatörü/sahibi (kullanıcının kendisi).

## Hedef (Neden)
`whapi-tamamen-kaldir` görevinde (Saga #357) Whapi'nin grup listeleme API'si kaldırıldı, bu panelin "kayıtsız grupları tara/ekle" özelliğini de birlikte götürdü (Baileys'in o zaman bu yeteneği yoktu, bilinçli kapsam dışı bırakılmıştı). Operatör yeni WhatsApp gruplarını (henüz `data/chat_groups.json`'a kaydedilmemiş) keşfedip panelden ekleyebilmek istiyor — bu artık Baileys'in kendi API'si üzerinden yapılacak.

## User Story
As a sistem operatörü
I want panelde WhatsApp'a (Baileys üzerinden) üye olduğum tüm grupları görüp, henüz kayıtlı olmayanları tek tıkla ekleyebilmek
So that Whapi'ye ihtiyaç duymadan yeni grupları keşfedip sisteme dahil edebileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given Baileys bağlı (authenticated), When bridge.js periyodik olarak (60 saniyede bir) `sock.groupFetchAllParticipating()` çağırır, Then sonuç `data/baileys_groups.json`'a (mevcut `writeQrState`/`writeAuthenticatedState` deseniyle, atomic write) yazılır.
2. [Critical] Given panelde login'li bir operatör, When `GET /api/whatsapp/groups` çağrılır ve `data/baileys_groups.json` mevcutsa, Then `200 + {"groups": [{"id":..., "name":..., "saved": true/false}], "cached": bool}` döner — `saved` alanı `data/chat_groups.json`'daki mevcut kayıtlarla karşılaştırılarak hesaplanır (eski Whapi route'unun response şekliyle BİREBİR aynı, panel frontend'i değişmeden çalışsın diye).
3. [High] Given Baileys bağlı değil (need_auth/waiting durumunda, `data/baileys_qr.json`'daki `status` alanı `authenticated` değilse), When `/api/whatsapp/groups` çağrılır, Then `202 + {"groups": [], "message": "WhatsApp henüz bağlı değil"}` döner (mevcut `/api/whatsapp/qr`'ın "waiting" desenindeki 202 kullanımıyla tutarlı).
4. [High] Given `data/baileys_groups.json` hiç yok (bridge.js henüz ilk taramayı yapmamış), When `/api/whatsapp/groups` çağrılır, Then `202 + {"groups": [], "message": "Gruplar henüz taranmadı, bridge başlıyor olabilir"}` döner.
5. [Medium] Given `sock.groupFetchAllParticipating()` bridge.js'te hata verir (network/rate limit), When periyodik tarama başarısız olur, Then bridge.js ESKİ dosyayı (varsa) SİLMEZ/BOZMAZ — bir sonraki periyodik denemede tekrar dener, hata sadece log'a düşer (panel bir önceki başarılı taramayı göstermeye devam eder).
6. [Medium] Given `data/baileys_groups.json` bozuk JSON içeriyor (yarım yazma vb.), When `/api/whatsapp/groups` çağrılır, Then `200 + {"groups": [], "cached": false}` döner (500 DEĞİL — mevcut `/api/whatsapp/qr`'ın "bozuk JSON → waiting" davranış deseniyle tutarlı, panel çökmez).
7. [Low] Given panelde "Grupları Yenile" butonu, When tıklanır, Then sadece `GET /api/whatsapp/groups`'u tekrar çağırır (bridge.js'e HİÇBİR sinyal göndermez — periyodik tarama zaten en fazla 60 saniyede bir güncel veri sağlıyor, ayrı bir "hemen tara" tetikleme mekanizması kapsam dışı, bkz. Kapsam Dışı).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (bridge periyodik tarama yaptı, panel okuyor) | `200 + {"groups":[...],"cached":true}` | yok (salt okuma) | Grup listesi, kayıtlı olanlar işaretli | AC-1, AC-2 |
| 2 | Baileys bağlı değil | `202 + {"groups":[],"message":"..."}` | yok | "WhatsApp henüz bağlı değil, önce QR taratın" mesajı | AC-3 |
| 3 | Kaynak yok (dosya hiç yok, ilk tarama bekleniyor) | `202 + {"groups":[],"message":"..."}` | yok | "Gruplar taranıyor, lütfen bekleyin" mesajı | AC-4 |
| 4 | Yetkisiz erişim | `401 + {"error":"Yetkisiz"}` | yok | Panel login ekranına yönlendirir | (mevcut `require_auth` deseni, ayrı AC gerekmiyor) |
| 5 | Dış bağımlılık hatası (bridge.js'in Baileys API çağrısı başarısız) | Bridge.js tarafında: log'a düşer, dosya değişmez. Panel tarafında: bir önceki `200 + {"groups":[...],"cached":true}` dönmeye devam eder | yok | Kullanıcı fark etmez (bir önceki başarılı veri gösterilir) | AC-5 |
| 6 | **Kısmi başarı** (dosya var ama bozuk JSON) | `200 + {"groups":[],"cached":false}` | yok | Boş liste + "cached: false" (frontend bunu "yenileniyor" gibi yorumlayabilir) | AC-6 |
| 7 | **Hiçbir şey yapılamadı ama hata da yok** | N/A — her çağrı 4 durumdan birine (200/202/401/200-boş) kesin düşer, "sessiz hiçbir şey dönmeme" durumu yok | — | — | Silindi: state machine'de böyle bir dal yok (panel-baileys-qr-gosterimi görevindeki AYNI gerekçe) |

Kısmi başarı: Bozuk JSON durumu `cached:false` ile "waiting"e benzer bir duruma düşürülür, 500 asla dönmez.
Hiçbir şey yapılamadı ama hata da yok: Uygulanamaz — yukarıda gerekçelendirildi.
Boş sonuç ↔ hata ayrımı: "Baileys bağlı değil" (202) ile "yetkisiz" (401) ile "gerçekten hiç grup yok" (200 + boş dizi, teorik) durum kodu ve `message` alanıyla ayrılıyor.

## Test Strategy
Unit: 70% — `/api/whatsapp/groups` endpoint'inin dosya okuma/parse/durum mantığı (mevcut `/api/whatsapp/qr` testlerindeki AYNI teknik: `patch.object` ile dosya yolu mock'lama), bridge.js'in `writeGroupsState()` (yeni, `writeQrState` deseniyle) fonksiyonunun atomic write davranışı.
Integration: 20% — gerçek Flask test client ile login'li/login'siz istek, dosya var/yok/bozuk senaryoları, `data/chat_groups.json` ile `saved` alanı karşılaştırması.
E2E: 10% — panelde "Grupları Yenile" butonunun gerçek tarayıcıda çalıştığını, layout'un bozulmadığını doğrulama (önceki görevlerde bu panel dosyasında canlı testte JS hataları bulunmuştu, aynı titizlik).

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: <500ms (endpoint sadece dosya okuyor, network call yok)
Memory: yok
Görsel/UI kriteri: "Kayıtsız grup" listesi ve "Ekle" butonları eski Whapi bölümüyle görsel olarak tutarlı render olmalı, layout bozulmamalı — `verify` adımında canlı tarayıcıyla kontrol edilecek.
Diğer ölçülebilir kriterler: bridge.js'in periyodik taraması 60 saniyede bir (± birkaç saniye toleransla) çalışmalı.

## Kapsam Dışı
- Grup üyelerini listeleme, grup açıklaması/profil resmi çekme.
- Grup oluşturma/silme (Baileys üzerinden WhatsApp grubu yönetimi) — sadece MEVCUT grupları listeleme.
- "Hemen tara" (bridge.js'e canlı sinyal gönderen) bir tetikleme mekanizması — periyodik (60sn) tarama yeterli kabul edildi, flag-dosyası/HTTP-sinyal gibi ek bir process-arası iletişim katmanı EKLENMEYECEK (CAVEMAN — Haiku alt-ajanının önerdiği flag-dosyası mekanizması orkestratör tarafından REDDEDİLDİ, bkz. Assumptions).
- Otomatik grup ekleme (tüm kayıtsız grupları toplu ekleme) — sadece tek tek "Ekle" butonu (mevcut `/api/groups` POST endpoint'i zaten bunu yapıyor, değişmeyecek).

## Etkilenen Dosyalar/Modüller (bilinen)
- `sidecar/bridge.js` — `writeGroupsState()` fonksiyonu (yeni, `writeQrState` deseniyle) + periyodik `setInterval` (60sn, sadece `connection === 'open'` sonrası aktif) eklenir.
- `src/api/admin_panel.py` — yeni route `GET /api/whatsapp/groups` (`@require_auth`), `INDEX_HTML`'e "kayıtsız grup tara/ekle" bölümü (whapi-tamamen-kaldir'de silinenin benzeri, ama artık `/api/whatsapp/groups`'u çağırıyor) geri eklenir.
- `data/baileys_groups.json` — yeni, bridge.js'in yazdığı dosya (mevcut `data/baileys_qr.json` deseniyle tutarlı).

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — önceki görevlerde bu makinede git reposu kökünün proje klasörüyle örtüştüğü gözlemlendi. Sonraki adımlar Grep/Glob çağrılarını gerçek proje klasörüyle sınırlamalı.

## Rollback Beklentisi
Bridge.js'in periyodik taraması başarısız olursa dosya BOZULMAZ/SİLİNMEZ (satır 5) — panel her zaman bir önceki başarılı veriyi (varsa) göstermeye devam eder. `/api/groups` (kayıtlı gruplar, whapi-tamamen-kaldir'den beri Whapi'ye hiç bağımlı değil) bu özellikten TAMAMEN bağımsız, hiçbir şekilde etkilenmez.

## Risks
- `sock.groupFetchAllParticipating()`'in Baileys kütüphanesindeki gerçek davranışı (rate limit, büyük grup sayısında performans) doğrulanmadı — `plan` adımında Baileys dokümantasyonu/mevcut `bridge.js` kodu okunarak netleştirilecek.
- 60 saniyelik periyot keyfi bir varsayım (Haiku'nun 5 dakika önerisinden orkestratör tarafından düşürüldü, "Grupları Yenile" butonunun gerçekten yeni veri getirebilmesi için makul bir tazelik sağlamak amacıyla) — kullanıcı onayı bekliyor.

## Assumptions
- **Flag-dosyası/HTTP-sinyal tetikleme mekanizması REDDEDİLDİ**: Haiku alt-ajanı "Grupları Tara" butonunun bridge.js'e bir flag dosyası yazıp anlık tetikleme yapmasını önerdi. Orkestratör bunu REDDETTİ — bu, iki ayrı process arasında (admin_panel.py/Python, bridge.js/Node) ek bir senkronizasyon katmanı ve yeni bir "yarış durumu" riski yaratır (tam da panel-baileys-qr-gosterimi görevinde `data/baileys_qr.json` için yaşanan zorluğun aynısı). Bunun yerine, bridge.js zaten bağlıyken kendi başına periyodik (60sn) tarama yapar — mevcut basit "yaz + oku" deseninin (QR, authenticated state) doğrudan devamı, CAVEMAN'a daha uygun.
- Periyot 60 saniye olarak varsayıldı (Haiku'nun 5 dakika önerisinden düşürüldü) — kullanıcı onayı bekliyor, `plan` adımından önce düzeltilebilir.
- Response şekli eski Whapi route'uyla (`{"groups":[...],"cached":bool}`) BİREBİR aynı tutuldu ki panel frontend'inin JS'i (whapi-tamamen-kaldir'de silinen `loadAvailableGroups()`/`grpAdd()` fonksiyonlarının benzerleri) minimal değişiklikle geri eklenebilsin.

## Unknowns
- Baileys'in `groupFetchAllParticipating()` fonksiyonunun tam dönüş şekli (`plan` adımında `sidecar/node_modules/@whiskeysockets/baileys` kütüphanesinin tip tanımları veya dokümantasyonu okunarak netleşecek).

## Sorular ve Cevaplar (ham kayıt)
(Haiku alt-ajanı tarafından yanıtlandı — general-purpose agent, model: haiku)
1-3. Happy path/tetikleme/tazelik → Haiku "flag dosyası + periyodik" hibrit önerdi, orkestratör flag dosyasını REDDEDİP sadece periyodik (60sn) tarama kararı verdi (basitlik, CAVEMAN).
4. Baileys bağlı değilse → Haiku 503 önerdi, orkestratör mevcut `/api/whatsapp/qr` deseniyle tutarlılık için 202'ye çevirdi.
5. `groupFetchAllParticipating()` hatası → son başarılı veri korunur, dosya bozulmaz.
6. Hiç grup yoksa → `200 + {"groups":[],"cached":true}` (teorik, gerçek olmayan senaryo).
7-9. Davranış sözleşmesi → yukarıdaki tabloya işlendi (202/200/401 kodlarıyla, Haiku'nun 503 önerisi 202'ye çevrildi).
10. Test oranı → 70/20/10 (Haiku önerisi, önceki görevle tutarlı, kabul edildi).
11. Kapsam dışı → üye listeleme, grup yönetimi, flag-tetikleme mekanizması (orkestratör tarafından eklendi), toplu ekleme.
12. Rollback → tarama hatası izole, "Kayıtlı Gruplar" hiç etkilenmez.
