---
task_slug: baileys-sidecar-webhook-secret-header
jira_id: null
saga_task_id: 381
threat_model: done
priority: critical
coverage_target: 70
performance_target: null
memory_target: null
test_strategy:
  unit: 60
  integration: 40
  e2e: 0
affected_modules:
  - sidecar/bridge.js
---

# ATDD — baileys-sidecar-webhook-secret-header

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #381 (epic #54 "Güvenlik Açığı Düzeltmeleri", critical).

## Persona
`mavi-baileys-bridge` PM2 process'i — otonom Node.js sidecar, insan etkileşimi yok.

## Hedef (Neden)
**ACİL — Production kesintisi:** `webhook_server.py`, önceki bir güvenlik görevinde (`65c9fe6`) bilinçli olarak `WEBHOOK_SHARED_SECRET` header kontrolünü fail-closed yaptı (secret uyuşmazsa 403). Ancak `sidecar/bridge.js`'in `postToWebhook()` fonksiyonu bu header'ı hiç göndermiyor. Sonuç: VPS'te gerçek gelen tüm WhatsApp mesajları şu an 403 ile reddediliyor (canlı log kanıtı: `Webhook auth failed: secret mismatch (secret=False, header=False)`) — hem sidecar HEM webhook_server.py tarafında secret tanımsız, mesaj kaybı riski.

## User Story
As a sistem (otonom sidecar)
I want gönderdiğim her webhook isteğine WEBHOOK_SHARED_SECRET header'ını eklemek
So that webhook_server.py isteği kabul edip mesajı işleyebilsin, gerçek WhatsApp mesajları kaybolmasın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `WEBHOOK_SHARED_SECRET` ortam değişkeni tanımlı, When `postToWebhook(messages)` çağrılır, Then fetch isteğinin `headers` objesinde `X-Webhook-Secret: <secret değeri>` bulunur (mock fetch ile assert edilebilir).
2. [Critical] Given `WEBHOOK_SHARED_SECRET` tanımsız/boş, When `postToWebhook(messages)` çağrılır, Then header gönderilmez/boş kalır (sunucu zaten fail-closed 403 döner — bu webhook_server.py'nin sorumluluğu), AMA bridge.js sessiz kalmaz: process başlangıcında (her istekte değil) konsola net bir uyarı loglanır.
3. [High] Given ağ hatası (webhook_server.py ayakta değil), When `postToWebhook` çağrılır, Then mevcut try/catch davranışı (satır 114-116) DEĞİŞMEDEN çalışır — bu görev bunu değiştirmiyor.
4. [Critical] **AC-S1 (threat-model)** — Given `WEBHOOK_SHARED_SECRET` tanımlı bir değere sahip, When bridge.js herhangi bir `console.log`/`console.error`/`console.warn` çağrısı yaparsa (happy path, hata, veya uyarı loglarında), Then secret'in GERÇEK DEĞERİ hiçbir log çıktısında görünmez — sadece "tanımlı/tanımsız" bilgisi geçebilir.
5. [Medium] Given kod değişikliği VPS'e deploy edilir ama `.env`'e `WEBHOOK_SHARED_SECRET` henüz eklenmemiş, When bridge.js çalışır, Then çökme olmaz, mevcut 403 davranışı sürer (regresyon yok) — bu, iki taraflı (kod + env) bir düzeltme olduğunu netleştirir.

## Threat Model
Çağrıldı — STRIDE-lite uygulandı (`sidecar/bridge.js`, dış API çağrısı + auth header ekleme). Sonuç: bu diff yeni bir güven sınırı açmıyor (webhook_server.py'nin auth mantığı değişmiyor, sadece gönderen taraf eksik header'ı tamamlıyor); Spoofing/Tampering/Repudiation/DoS/Elevation bu değişikliğe uymuyor. Info Disclosure kategorisinden **AC-S1** çıktı — secret değerinin yanlışlıkla log'a yazılmaması, somut ve test edilebilir tek güvenlik kriteri (kullanıcının kendi netleştirme cevabında da açıkça istenmişti).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (secret tanımlı) | Sunucudan 200 | Header eklenir, mesaj işlenir | `[WEBHOOK OK] N mesaj gönderildi` | AC-1 |
| 2 | Secret tanımsız | Sunucudan 403 (webhook_server.py'nin mevcut davranışı) | Header gönderilmez | Process başında bir kez uyarı + mevcut `[WEBHOOK HATA] 403` | AC-2 |
| 3 | Ağ hatası | Yok (exception yakalanır) | Yok | `[WEBHOOK BAGLANTI HATASI] ...` (mevcut, değişmedi) | AC-3 |
| 4 | Zaman aşımı | Uygulanmıyor | — | — | Native fetch varsayılan davranışı, kapsam dışı |
| 5 | Kısmi başarı | Uygulanmıyor | — | — | Tek atomik HTTP isteği, kısmi senaryo yok |
| 6 | Hiçbir şey yapılamadı ama hata yok | Uygulanmıyor | — | — | Her durum (200/403/ağ hatası) loglanıyor, sessiz başarı senaryosu kodda mevcut değil |
| 7 | Secret log'a sızması (AC-S1) | — | Yok | Log'da sadece "tanımlı/tanımsız", asla gerçek değer | AC-S1 |

Kısmi başarı: Uygulanmıyor (tek `fetch` çağrısı, atomik).
Hiçbir şey yapılamadı ama hata da yok: Uygulanmıyor — her sonuç (200/403/ağ hatası) zaten loglanıyor, bu görev buna dokunmuyor.
Boş sonuç ↔ hata ayrımı: N/A — bu fonksiyon veri sorgulamıyor, tek yönlü bir POST isteği.

## Test Strategy
Unit: 60% — `sidecar/test_bridge_reliability.js` ile aynı desende (Node built-in `assert`, `require('./bridge.js')`, `module.exports`'a eklenecek yeni bir test edilebilir helper, örn. header oluşturma mantığı ayrı bir fonksiyona çıkarılıp mock'lanabilir hale getirilirse) veya doğrudan `postToWebhook`'u export edip global `fetch`'i mock'layarak header'ın içeriğini assert etme.
Integration: 40% — gerçek bir local HTTP sunucusuna (basit bir Node/Python test sunucusu, `sidecar/manual_webhook_test_server.py` deseni referans alınabilir) karşı `postToWebhook` çağrılıp gelen isteğin header'ının gerçekten `X-Webhook-Secret` içerdiğinin doğrulanması.
E2E: 0% — VPS'e gerçek deploy sonrası doğrulama, kullanıcının SSH ile yapacağı manuel bir adım (bu pipeline'ın kapsamı dışında, `verify`/`red-team` sonrası kullanıcıya deploy adımı olarak verilecek).

## Benchmark / Başarı Ölçütü
Coverage Target: 70%
Performance Target: Yok
Memory: Yok
Görsel/UI kriteri: Yok (backend/altyapı görevi, UI yok).
Diğer ölçülebilir kriterler: Deploy sonrası VPS'te `pm2 logs mavi-baileys-bridge` ve `pm2 logs mavi-lojistik-server`'da "secret mismatch" uyarılarının kesilmesi (kullanıcı tarafından gözlemlenecek, bu pipeline'ın son doğrulaması değil).

## Kapsam Dışı
- `webhook_server.py`'nin (alıcı taraf) auth mantığını değiştirmek — zaten doğru çalışıyor, dokunulmuyor.
- Gerçek `WEBHOOK_SHARED_SECRET` değerini üretmek ve VPS `.env`'e yazmak — bu CLI ortamından SSH ile VPS dosyasına yazılamıyor, kullanıcıya SSH komutu olarak verilecek (deploy adımı).
- Whapi entegrasyonunun header göndermesi — ayrı bir entegrasyon, bu görev sadece Baileys sidecar'ı (`bridge.js`) kapsıyor.
- `tests/test_webhook_shared_secret_auth.py` (webhook_server.py tarafı testleri) — DEĞİŞMEYECEK, sadece regresyon garantisi.

## Etkilenen Dosyalar/Modüller (bilinen)
- `sidecar/bridge.js`: `postToWebhook()` fonksiyonu (satır 102-117), `module.exports` bloğu (satır 298-305, yeni bir test edilebilir helper eklenecekse)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu makinede git reposunun kökünün proje klasörüyle aynı olup olmadığı teyit edilmedi. Sonraki adımlarda arama `sidecar/`, `src/`, `tests/`, `obss_project/` gibi proje-içi dizinlerle sınırlı tutulmalı.

## Rollback Beklentisi
Geriye dönük uyumlu: header eklemek var olan davranışı bozmaz. `WEBHOOK_SHARED_SECRET` VPS'e henüz eklenmemişse bile bridge.js çökmeden çalışmaya devam eder, sadece mevcut 403 davranışı sürer (regresyon yok, sadece durum netleşir/loglanır). Kod önce deploy edilebilir, `.env` güncellemesi ayrı bir adımda yapılabilir.

## Risks
- Bu kod değişikliği VPS `.env`'e `WEBHOOK_SHARED_SECRET` eklenmeden tek başına deploy edilirse sorun HÂLÂ devam eder — iki taraf da (kod + env) güncellenmeli. Deploy sırasında kullanıcıya bu adım açıkça hatırlatılacak.
- `sidecar/` klasöründe resmi bir JS test runner (jest/vitest) yok, proje kendi `node <dosya>.js` + built-in `assert` konvansiyonunu kullanıyor (doğrulandı: `test_bridge_reliability.js`) — bu konvansiyona sadık kalınacak, yeni bir framework eklenmeyecek (CAVEMAN).

## Assumptions
- `.env.example`'daki `WEBHOOK_SHARED_SECRET=secret_buraya` placeholder'ının VPS'in gerçek `.env`'inde bir değerle DOLDURULMADIĞI varsayılıyor — canlı log kanıtı (`secret=False`) bunu destekliyor (webhook_server.py tarafında da env boş). Önceki Sonnet alt-ajanı cevabında yanlışlıkla "webhook_server.py tarafı zaten ayarlı olmalı" varsayımı yapılmıştı — bu, gerçek log kanıtıyla ÇELİŞİYOR ve düzeltildi: her iki taraf da (VPS `.env` + bridge.js'in kendi env'i, muhtemelen aynı `.env` dosyasından PM2 ile yükleniyor) tanımsız.
- `bridge.js`'in PM2 üzerinden `.env` dosyasını nasıl yüklediği (`dotenv` mi, PM2 `env` config'i mi) doğrulanmadı — `ecosystem.config.js` plan adımında incelenecek.

## Unknowns
- `sidecar/`'da resmi bir JS test framework'ü (jest/vitest/`node:test`) kurulu mu, yoksa sadece built-in `assert` + doğrudan `node` çalıştırma mı kullanılıyor — plan adımında `sidecar/package.json` kontrol edilecek (mevcut `test_bridge_reliability.js` örneği built-in `assert` kullanıyor, muhtemelen aynı desen sürecek ama kesinleştirilmedi).

## Sorular ve Cevaplar (ham kayıt)
1. Persona → PM2 process, otonom (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
2. Ana hedef → Production kesintisi, mesaj kaybı riski (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
3. Happy path → Header eklenir, 200 alınır (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
4. Edge case 1 (secret tanımsız) → Header gönderilmez, process başında bir kez uyarı loglanır (Sonnet 5 low alt-ajanı tarafından yanıtlandı: log spam'den kaçınma)
5. Edge case 2 (ağ hatası) → Değişmiyor, mevcut try/catch (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
6. Davranış sözleşmesi → Yukarıdaki tablo (Sonnet 5 low alt-ajanı tarafından yanıtlandı + threat-model AC-S1 eklendi)
7. Başarı ölçütü → Header içeriği mock fetch ile assert edilebilir (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → webhook_server.py, .env değeri üretme, Whapi tarafı (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar/test altyapısı → sidecar/bridge.js, JS test altyapısı doğrulanmadı → Unknowns'a taşındı, orkestratör tarafından `test_bridge_reliability.js` incelenerek built-in `assert` deseni doğrulandı
10. Güvenlik kısıtı → Secret değeri hiçbir log çağrısına yazılmamalı (Sonnet 5 low alt-ajanı tarafından yanıtlandı, AC-S1'e dönüştü)
11. Rollback → Geriye dönük uyumlu, çökme olmaz (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
12. Kabul kriteri sahibi → Kullanıcı, gerçek VPS doğrulaması gerekir (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
13. Test stratejisi → Unit 60/Integration 40/E2E 0, yüzde uydurulmadı (Sonnet 5 low alt-ajanı tarafından yanıtlandı + orkestratör tarafından sidecar/test_bridge_reliability.js deseni doğrulanarak netleştirildi)
14. Bilinen riskler → İki taraflı deploy gerekiyor; alt-ajanın "webhook_server.py tarafı zaten ayarlı" varsayımı gerçek log kanıtıyla çelişiyordu, düzeltildi (bkz. Assumptions)
