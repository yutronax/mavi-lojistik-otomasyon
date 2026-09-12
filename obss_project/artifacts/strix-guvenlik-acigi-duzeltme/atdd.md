---
task_slug: strix-guvenlik-acigi-duzeltme
jira_id: null
saga_task_id: 379
priority: critical
coverage_target: 85
performance_target: "webhook yanıt süresi mevcut davranışa göre gözle görülür artmamalı"
memory_target: null
test_strategy:
  unit: 70
  integration: 20
  e2e: 10
affected_modules:
  - src/api/admin_panel.py
  - src/api/webhook_server.py
---

# ATDD — strix-guvenlik-acigi-duzeltme

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task: #379 (epic #54 — Güvenlik Açığı Düzeltmeleri (Strix Bulguları)).

## Kaynak: strix-scan Bulguları
[strix_runs/api_d8ee/findings.sarif](../../../strix_runs/api_d8ee/findings.sarif) — `src/api` hedefinde quick modda çalıştırılan gerçek (dinamik) pentest taramasının sonucu.

## Persona
1. **Yönetici (mağdur/kurban):** admin_panel.py'yi açan, oturumu XSS ile ele geçirilebilecek kullanıcı. (kullanıcı mesajından/sarif)
2. **Saldırgan:** webhook endpoint'ine kimlik doğrulaması olmadan erişebilen, internetteki herhangi bir istemci. (kullanıcı mesajından/sarif)

## Hedef (Neden)
İki gerçek, dinamik olarak doğrulanmış güvenlik açığını kapatmak:
- Stored XSS → admin oturumunun ele geçirilip her `/api/*` eyleminin (servis restart, `.env` key okuma, sahte kargo onaylama) saldırgan tarafından tetiklenmesini önlemek.
- Kimlik doğrulamasız webhook enjeksiyonu → sahte kargo ilanlarının otomatik onaylanıp gerçek YukBurada platformuna gönderilmesini önlemek. (kullanıcı mesajından/sarif)

## User Story
As a maviLojistik operatörü/yöneticisi
I want admin panelin ve webhook endpoint'inin saldırgan kontrolündeki veriye karşı güvenli olmasını
So that oturumum ele geçirilmesin ve sahte kargo verisi sisteme giremesin

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given webhook'tan gelen bir `message_id` HTML/JS özel karakteri içeriyor, When admin panel `/` sayfasını render ediyor, Then `message_id` `data-mid` attribute'una `escapeHtml` ile yazılır ve `onclick` handler'ları `this.dataset.mid` kullanır — hiçbir sink'te ham interpolasyon kalmaz (satır 1601-1602, 1622, ve `openEditModal` için `data-mid="${escapeHtml(encodeURIComponent(mid))}"`).
2. [Critical] Given webhook isteği geçerli `X-Webhook-Secret` header'ı taşımıyor veya yanlış, When `do_POST` çağrılıyor, Then istek `hmac.compare_digest` ile reddedilip 403 döner ve işleme kuyruğuna hiçbir şey eklenmez.
3. [Critical] Given `WEBHOOK_SHARED_SECRET` ortam değişkeni tanımlı değil, When webhook'a herhangi bir istek gelir, Then sunucu çökmeden ayakta kalır ama tüm istekleri 403 ile reddeder (fail-closed, fail-open değil).
4. [High] Given geçerli secret ama beklenen JSON şekline uymayan gövde (`messages` listesi değil / obje değil), When `do_POST` çağrılıyor, Then 400 döner, istek loglanır, kuyruğa hiçbir şey eklenmez.
5. [High] Given geçerli secret + geçerli şekil, When `do_POST` çağrılıyor, Then 200 döner ve mesaj işleme kuyruğuna eklenir (mevcut davranış korunur).
6. [Medium] Given meşru (kötü niyetli olmayan) bir `message_id` HTML özel karakteri içeriyor, When admin panel render ediyor, Then veri reddedilmez, sadece güvenli şekilde escape edilerek görüntülenir.
7. [Medium] Given XSS düzeltmesi uygulandı, When opsiyonel CSP (`script-src 'self'`) eklenir, Then inline handler'lar dışındaki script çalıştırma girişimleri tarayıcı tarafından engellenir.

## Agentic Değerlendirme Kriterleri
Tetikleyici yok — bu görev bir LLM agent/tool-calling davranışını değiştirmiyor, bu bölüm silindi.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (geçerli secret + geçerli şekil) | 200 OK, `{"status":"ok"}` | Mesaj işleme kuyruğuna eklenir | Whapi/sidecar için normal başarı yanıtı, log'da kabul kaydı | AC-5 |
| 2 | Girdi geçersiz/eksik (JSON şekli beklenene uymuyor) | 400 Bad Request, hata mesajı gövdede | Kuyruğa hiçbir şey eklenmez, uyarı loglanır | Gönderen taraf hata kodu görür | AC-4 |
| 4 | Yetkisiz erişim (secret eksik/yanlış) | 403 Forbidden | Kuyruğa eklenmez, güvenlik logu | Gönderen taraf 403 görür; secret sidecar/Whapi'de güncellenmemişse entegrasyon bu noktada kesintiye uğrar (bkz. Rollback Beklentisi) | AC-2, AC-3 |
| 5 | Dış bağımlılık hatası (orchestrator/queue erişilemez) | 503 Service Unavailable | İstek reddedilir, retry gönderen tarafa bırakılır | Gönderen taraf 503 görür | — (mevcut davranış, bu görevle değişmiyor) |

Silinen satırlar:
- **Kaynak yok:** Uygulanamaz — webhook endpoint'i POST-only, "kaynak bulunamadı" kavramı REST CRUD şablonundan kalma, bu uç için anlamsız.
- **Zaman aşımı:** Bu görevin kapsamı dışı — mevcut orchestrator/queue zaman aşımı davranışı bu değişiklikle değişmiyor, ayrıca test edilmeyecek.
- **Kısmi başarı:** Uygulanamaz — webhook tek bir JSON gövdesini ya bütünüyle kabul eder ya reddeder; "kısmi" durum zaten AC-4/satır 2'deki şekil-doğrulama ile karşılanıyor, ayrı bir satıra gerek yok.

Hiçbir şey yapılamadı ama hata da yok: **Olmamalı — pazarlıksız.** Secret doğru + şekil geçerliyse mutlaka 200 + kuyruğa ekleme; secret doğru + şekil geçersizse mutlaka 400 (satır 2). Sessizce 200 dönüp hiçbir şey yapmama (mevcut kodun "always 200 önce, sonra işle" davranışı) açıkça YASAKLANIR — bu tam da mevcut açığın kökü, test-copilot bunu özellikle test etmeli.

Boş sonuç ↔ hata ayrımı: 403 (kimlik doğrulama başarısız) ile 400 (kimlik doğrulama başarılı ama veri şekli geçersiz) birbirinden kesin ayrılır — ikisi de "hiçbir şey işlenmedi" anlamına gelir ama HTTP status kodu ile hangi sebepten olduğu gönderen tarafa (ve loglara) net bildirilir.

## Test Strategy
Unit: 70% — `escapeHtml`/data-attribute render fonksiyonu, `hmac.compare_digest` secret kontrolü, JSON şekil doğrulama fonksiyonu (izole, saf mantık).
Integration: 20% — `do_POST` uçtan uca: geçerli/geçersiz secret, geçerli/geçersiz şekil kombinasyonlarının gerçek HTTP durum kodlarını döndürdüğünü doğrulamak.
E2E: 10% — admin panel render edilip XSS payload'lı bir `message_id`'nin tarayıcıda script çalıştırmadığını doğrulayan bir senaryo (varsa `vision-test`/Playwright ile).

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: webhook yanıt süresi mevcut davranışa göre gözle görülür artmamalı (hmac + şekil kontrolü mikrosaniye mertebesinde olmalı)
Memory: yok
Görsel/UI kriteri: admin panel düzeni bozulmamalı, XSS payload'lı `message_id` sayfada güvenli biçimde (kaçışlı) görünmeli — `verify` adımında mümkünse `vision-test` ile kontrol edilsin.
Diğer ölçülebilir kriterler: `/api/login` brute-force rate limiti (MAX_FAILED=5/30s) ve diğer `/api/*` auth kontrolleri bu değişiklikten etkilenmemeli (regresyon testiyle doğrulanmalı).

## Kapsam Dışı
- Baileys sidecar köprüsünün ve Whapi webhook kaydının `X-Webhook-Secret` header'ı göndermek üzere güncellenmesi — muhtemelen ayrı bir dil/repo, ayrı bir Saga görevi olarak açılmalı.
- Otomatik rollback/feature-flag mekanizması kurmak — bu görevin kapsamında değil, geçiş sıralaması kullanıcıya açıkça belirtilecek (bkz. Rollback Beklentisi).
- Zaman aşımı (timeout) davranışının değiştirilmesi — mevcut orchestrator/queue davranışı korunuyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` (satır 1601-1602, 1622 ve ilgili render fonksiyonu)
- `src/api/webhook_server.py` (`do_POST`)
- `.env` (yeni `WEBHOOK_SHARED_SECRET` değişkeni eklenecek)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu makinede git reposunun kökünün proje klasörüyle (maviLojistik) aynı olup olmadığı bu görev kapsamında test edilmedi. Sonraki adımlar (plan/code-copilot/test-copilot/red-team) arama/grep'i `src/api/` ve ilgili `.env`/config dosyalarıyla sınırlı tutmalı, kök dizinden sınırsız arama yapmamalı.

## Rollback Beklentisi
Secret kontrolü zorunlu ve kalıcı olacak (feature-flag yok) ama **devreye alma sırası kritik**: `WEBHOOK_SHARED_SECRET` önce Baileys sidecar'a ve Whapi kaydına eklenmeli (ayrı görev), ancak ondan sonra `webhook_server.py`'de zorunlu hale getirilmeli. Bu görev tek başına deploy edilirse ve sidecar/Whapi henüz header göndermiyorsa, gerçek webhook trafiği 403 ile kesintiye uğrar — bu risk kullanıcıya code-copilot/verify aşamasında açıkça hatırlatılacak, otomatik rollback bu görevin kapsamında değil.

## Risks
- Sidecar/Whapi güncellenmeden bu değişiklik production'a çıkarsa gerçek webhook trafiği kesintiye uğrayabilir (bkz. Rollback Beklentisi).
- `WEBHOOK_SHARED_SECRET` üretimi ve `.env`'e/sidecar'a eşzamanlı yayılması manuel bir adım — otomatikleştirilmedi.

## Assumptions
- `WEBHOOK_SHARED_SECRET` yeni, rastgele üretilecek bir değer (örn. `secrets.token_hex(32)`) olacak, mevcut bir secret yeniden kullanılmayacak. (Sonnet 5 low alt-ajanı tarafından yanıtlandı: production'da tek bir env değişkeninin eksikliği tüm servisi çökertmemeli, yeni secret üretimi standart pratik)
- Kabul kriteri sahibi kullanıcıdır — otomatik testler (verify/red-team) ön koşul, nihai onay kullanıcıdan. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)

## Unknowns
- Zaman aşımı (timeout) durumunda dönülecek kesin HTTP kodu (504 mü, 202+arka plan mı) — mevcut mimariye bakılmadan netleştirilemedi, kapsam dışı bırakıldı ama ileride tekrar gündeme gelebilir.

## Sorular ve Cevaplar (ham kayıt)
1. Kabul kriteri sahibi kimin onayı yeterli? → Kullanıcı onayı yeterli; otomatik testler ön koşuldur, nihai onay üründen sorumlu kişiden. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
2. Test stratejisi oranı? → 70/20/10 (unit/integration/e2e), coverage %85 — güvenlik mantığı çoğunlukla izole edilebilir birim, webhook akışı entegrasyon testiyle doğrulanmalı. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
3. Kapsam dışı — Baileys sidecar/Whapi güncellemesi ve CSP? → Sidecar/Whapi güncellemesi kapsam dışı (ayrı görev); CSP header kapsamda (düşük riskli, XSS düzeltmesinin doğal tamamlayıcısı). (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
4. Kısmi başarı — secret tanımlı değilse ne olmalı? → Fail-closed ama ayakta kalsın: sunucu çökmesin, tüm webhook isteklerini 403 ile reddetsin. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
5. Hiçbir şey yapılamadı ama hata da yok durumu? → Secret doğru ama şekil geçersizse 400 dönülmeli ve loglanmalı, sessizce 200 dönülmemeli. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
6. Meşru HTML özel karakteri içeren message_id? → Reddedilmesin, sadece escape edilsin. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
7. Rollback beklentisi? → Zorunlu ama kontrollü geçiş: önce sidecar/Whapi güncellensin (ayrı görev), sonra webhook_server.py'de zorunlu hale getirilsin; otomatik rollback kapsam dışı. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
8. Performans/güvenlik kısıtı — mevcut rate limit etkilenir mi? → Etkilenmemeli, webhook endpoint'inden bağımsız bir kod yolu; ek performans etkisi mikrosaniye mertebesinde, pratikte yok. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. WEBHOOK_SHARED_SECRET nereden gelecek? → Mevcut .env dosyasına yeni, rastgele üretilmiş bir değer eklenecek. (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
