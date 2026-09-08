---
task_slug: webhook-server-threading-fix
jira_id: null
saga_task_id: null
priority: critical
coverage_target: 75
performance_target: "eşzamanlı istek 1sn altında yanıtlanmalı (bir bağlantı 60sn'ye kadar takılıyken)"
memory_target: null
test_strategy:
  unit: 20
  integration: 70
  e2e: 10
affected_modules:
  - src/api/webhook_server.py
---

# ATDD — webhook-server-threading-fix

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (canlı ortamda gözlemlenen bir kesinti sonrası).

## Saga Kaynağı
Saga'ya bağlı değil — bu ortamda `project_id` bilinmiyor/yapılandırılmamış.

## Persona
VPS'i işleten operatör/geliştirici — sistemi ayakta tutan ve WhatsApp mesaj akışına güvenen kişi. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## Hedef (Neden)
Canlıda `webhook_server.py`'nin tek-thread'li `http.server.HTTPServer`'ı bir isteğin (`do_POST`'taki `rfile.read`/`wfile.write`) takılmasıyla TAMAMEN tıkandı — port `LISTEN` durumda kaldı ama hiçbir isteğe (health check dahil) yanıt vermedi, `mavi-baileys-bridge` webhook'a "fetch failed" alıyordu, yeni WhatsApp mesajları hiç işlenmiyordu. Sadece `pm2 restart` ile geçici çözüldü. Hedef: veri kaybı/gecikme riskini önlemek — bu doğrudan operasyonel/müşteri güveni riski. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## User Story
As a VPS operatörü
I want webhook sunucusunun bir bağlantının takılmasından etkilenmeden diğer istekleri işlemeye devam etmesini
So that tek bir yavaş/bozuk istek yüzünden WhatsApp mesaj akışı tamamen durmasın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given webhook sunucusu `ThreadingHTTPServer` (veya eşdeğer `socketserver.ThreadingMixIn` karışımı) kullanıyor, When bir istek (A) `rfile.read()`'de kasıtlı olarak takılırsa (örn. eksik/yavaş body gönderen bir istemci), Then aynı anda gelen ikinci bir istek (B) A'nın bitmesini beklemeden, 1 saniyeden kısa sürede yanıtlanır.
2. [Critical] Given her client soket'ine bir `timeout` (30 saniye) atanmış, When bir bağlantı bu süre boyunca veri göndermez/almazsa, Then bağlantı `socket.timeout` ile kapatılır, sunucunun geri kalanı (diğer bağlantılar/thread'ler) etkilenmez.
3. [High] Given mevcut `except Exception` hata yakalama davranışı, When bozuk JSON veya eksik `Content-Length` gelirse, Then mevcut davranış (500 dönme, hata loglama) DEĞİŞMEDEN korunur — threading geçişi bu davranışı etkilemez.
4. [Medium] Given `_handle_baileys_event`'in kendi içinde zaten ayrı bir `threading.Thread` açtığı ("thread içinde thread" deseni), When `ThreadingHTTPServer`'a geçilirse, Then bu iç içe thread yapısı ek bir mimari sorun yaratmaz (her ikisi de kısa ömürlü, I/O-bound) — ayrı bir optimizasyon (tek thread havuzuna indirme) bu görevin kapsamı dışında bırakılır.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (normal webhook isteği) | 200 + `{"status": "received"}` | Arka planda `_handle_baileys_event` çalışır | Gecikmesiz yanıt | AC-1 |
| 2 | Girdi geçersiz/eksik (bozuk JSON) | 500 (mevcut davranış, değişmiyor) | Hata loglanır | Webhook gönderen taraf hata görür | AC-3 |
| 3 | Zaman aşımı (bir bağlantı 30sn boyunca veri göndermez/almaz) | `socket.timeout`, bağlantı kapanır | Sadece o bağlantı etkilenir, diğerleri devam eder | Webhook gönderen taraf bağlantı kesilmesi görür (yeniden dener) | AC-2 |
| 4 | Hiçbir şey yapılamadı ama hata yok ("sessiz ölüm" — sunucu LISTEN ama yanıt yok) | N/A — bu görev kök nedeni (thread tıkanması) düzeltiyor, tespit/monitoring ayrı bir görev | — | — | — |

Satırlar "Kaynak yok" (HTTP sunucusunda dosya/kayıt kavramı yok), "Yetkisiz erişim" (webhook endpoint'i auth'suz, sadece localhost/iç ağdan erişiliyor), "Dış bağımlılık hatası" (bu görev sunucunun kendi dayanıklılığıyla ilgili, dışarıya çağrı yapmıyor), "Kısmi başarı" (tek HTTP isteği ya tam yanıtlanır ya bağlantı kesilir) silindi — hiçbiri bu görevin kapsamında anlamlı bir davranış değişikliği gerektirmiyor. (Sonnet 5 alt-ajanı gerekçesi)

Kısmi başarı: Uygulanmıyor (bkz. yukarı).
Hiçbir şey yapılamadı ama hata da yok: Bu, tam olarak yaşanan olayın kendisi (sunucu "LISTEN" görünüp yanıt vermiyor) — bu görev kök nedeni (tek-thread tıkanması) ortadan kaldırıyor, ama "bu bir daha olursa erken fark etme" (health-check/monitoring) AYRI bir görev olarak bırakılıyor (bkz. Kapsam Dışı).
Boş sonuç ↔ hata ayrımı: N/A — HTTP sunucusu boolean/veri döndürmüyor, bu ayrım bağlamı yok.

## Test Strategy
Unit: 20% — sınıfın doğru mixin'den (`ThreadingMixIn`) türediğinin, `timeout` değerinin doğru set edildiğinin kontrolü.
Integration: 70% — gerçek `ThreadingHTTPServer` başlatıp gerçek soket üzerinden: (a) bir bağlantıyı kasıtlı geciktirip aynı anda ikinci bağlantının hızlı yanıtlandığını, (b) 30sn timeout'un gerçekten tetiklendiğini doğrulayan testler. (Sonnet 5 alt-ajanı gerekçesi: asıl risk gerçek soket davranışı, unit test bunu yakalayamaz)
E2E: 10% — VPS'te PM2 ile canlı doğrulama (deploy sonrası manuel/scripted health check).

## Benchmark / Başarı Ölçütü
Coverage Target: 75%
Performance Target: Bir istek kasıtlı olarak 60 saniye geciktirilirken, aynı anda gelen ikinci bir isteğin 1 saniyeden kısa sürede yanıtlanması.
Memory: yok
Diğer ölçülebilir kriterler: 30 saniyelik soket timeout'unun gerçekten çalıştığı (bağlantının bu süre sonunda kapatıldığı) entegrasyon testiyle kanıtlanmalı.

## Kapsam Dışı
- Rate limiting eklemek.
- Authentication eklemek (webhook endpoint'i mevcut haliyle auth'suz kalacak, sadece localhost/iç ağdan erişiliyor).
- `webhook_server.py`'nin genel mimarisini (endpoint yapısı, orchestrator entegrasyonu, `_handle_baileys_event`'in kendi thread açma deseni) değiştirmek.
- Health-check/monitoring altyapısı kurmak ("sessiz ölüm"ü erken tespit etme) — ayrı bir görev olarak önerilecek, bu görevde yapılmayacak.
- Thread havuzuna geçiş gibi ek optimizasyonlar (iç içe thread yapısını "düzeltme").

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/webhook_server.py` (`WhapiWebhookHandler` sınıfı, `run_server()` fonksiyonu)
- `vps_main.py` gibi bu dosyayı çağıran yerler — sadece import/instantiation şekli değişmediği sürece etkilenmemeli, `plan` aşamasında grep ile teyit edilecek.

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu worktree'nin git kökü proje klasörüyle aynı görünüyor, ancak daha geniş bir dizin/devasa git geçmişi olup olmadığı ayrıca doğrulanmadı. Aramalar `src/api/webhook_server.py`, `vps_main.py` ve `tests/` ile sınırlı tutulmalı.

## Rollback Beklentisi
Basit `git revert` ile `HTTPServer`'a geri dönülebilir olmalı — değişiklik küçük kapsamlı (sınıf değişimi + timeout eklemesi) olduğundan düşük risk. PM2 üzerinden `pm2 restart` ile hemen eski davranışa dönülebilir, ekstra veri taşıma/migration gerekmiyor. (Sonnet 5 alt-ajanı gerekçesi)

## Risks
- Sadece `ThreadingHTTPServer`'a geçmek TEK BAŞINA yeterli değil — client soket'lerine timeout eklenmezse, sınırsız sayıda yavaş/kötü niyetli bağlantı sınırsız thread açıp kaynak (thread/bellek) tüketmeye devam edebilir (yavaş DoS riski). Bu görev ikisini BİRLİKTE yapmalı (Sonnet 5 alt-ajanı, Soru 4).
- "Sessiz ölüm" durumunun (LISTEN ama yanıt yok) bir daha fark edilmeden saatlerce sürmesi riski bu görevle tam olarak giderilmiyor — kök neden düzeltiliyor ama erken tespit mekanizması (monitoring) kapsam dışı, ayrı bir görev olarak takip edilmeli.

## Assumptions
- 30 saniyelik soket timeout değeri makul bir varsayılan olarak kabul edildi — kullanıcı farklı bir süre belirtmedi, bu bir varsayımdır.
- `vps_main.py`'nin `webhook_server.py`'yi nasıl çağırdığı (import şekli) henüz doğrulanmadı — `plan` aşamasında kontrol edilecek.

## Unknowns
- `vps_main.py`'nin `make_webhook_handler_class()` veya `run_server()`'ı çağırma şeklinin, `ThreadingHTTPServer`'a geçişten etkilenip etkilenmeyeceği `plan` aşamasında netleştirilmeli.
- Mevcut projede zaten bir health-check/cron mekanizması olup olmadığı bilinmiyor (Soru 12) — varsa gelecekteki monitoring görevi ona entegre olmalı, yoksa sıfırdan tasarlanmalı (bu görevin kapsamı dışı).

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü / persona → VPS operatörü/geliştirici (Sonnet 5 alt-ajanı tarafından yanıtlandı)
2. Ana hedef / neden → Veri kaybı/gecikme riskini önlemek (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Happy path → İkinci istek birincinin bitmesini beklemeden hızlı yanıtlanır (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. Edge case (kötü niyetli/yavaş istemci) → Threading TEK BAŞINA yetmez, timeout da gerekli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
5. Edge case (thread içinde thread) → Kabul edilebilir, ek sorun yaratmaz (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Davranış sözleşmesi tablosu → yukarıdaki tabloya işlendi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
7. Başarı ölçütü → 60sn geciktirilen istek varken 2. istek <1sn'de yanıtlanmalı (Sonnet 5 alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → rate limiting, auth, mimari değişiklik, monitoring (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → webhook_server.py öncelikli, vps_main.py grep ile teyit edilecek (Sonnet 5 alt-ajanı tarafından yanıtlandı)
10. Test stratejisi → %20 unit / %70 integration / %10 e2e (Sonnet 5 alt-ajanı tarafından yanıtlandı)
11. Rollback beklentisi → git revert + pm2 restart yeterli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
12. Monitoring/gözlemlenebilirlik → ayrı bir görev, bu kapsamda değil (Sonnet 5 alt-ajanı tarafından yanıtlandı)
