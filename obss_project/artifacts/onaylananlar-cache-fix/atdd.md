---
task_slug: onaylananlar-cache-fix
jira_id: null
saga_task_id: null
priority: high
coverage_target: 85
performance_target: "onay işlemi O(1) bellek/CPU (dosya boyutundan bağımsız)"
memory_target: "mavi-admin-panel süreci, art arda 50+ onay sonrası 200MB altında stabil"
test_strategy:
  unit: 80
  integration: 20
  e2e: 0
affected_modules:
  - src/api/admin_panel.py
---

# ATDD — onaylananlar-cache-fix

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (canlı VPS log/bellek incelemesinden doğdu).

## Persona
Panel'i kullanan operasyon ekibi (web/mobil arayüzden tekli/toplu onay yapan) ve
sunucu-taraflı otomatik onay döngüsü (`_auto_approve_loop`, her 3 saniyede bir
tetiklenebilir). İkisi de aynı iki fonksiyonu (`unprocessed_approve`,
`_approve_message`) çağırıyor.

## Hedef (Neden)
`data/Onaylananlar.json` 143MB'a ulaştı (31.403 kayıt) ve her onay işleminde
(`unprocessed_approve` ve `_approve_message`) bu dosyanın TAMAMI diskten okunup
Python objelerine çevriliyor, bir kayıt eklenip TAMAMI tekrar JSON'a serialize
edilip diske yazılıyor. `_auto_approve_loop` bunu 3 saniyede bir tetikleyebiliyor.
Bu, `mavi-admin-panel` PM2 sürecinin belleğini 672MB'a (700MB limitine yakın)
taşıyor — dosya büyümeye devam ettikçe kötüleşecek. Zaten aynı dosyada
`onaylanmamis_ayristirilmis.json` için çalışan bir in-memory cache pattern'i
(`_unprocessed_cache`) var; aynı yaklaşım `Onaylananlar.json` için de
uygulanacak.

## Kod Keşfinde Doğrulanan Kritik Bulgu
`Onaylananlar.json` (büyük O, 143MB) **SADECE `src/api/admin_panel.py`
tarafından** okunup yazılıyor — Grep ile proje genelinde doğrulandı. Benzer
isimli `onaylanan_kayitlar.json` (küçük harf, 1.3MB), `src/services/data_service.py`
üzerinden masaüstü uygulaması (`masaustu_uygulama.py`) tarafından kullanılan
**tamamen ayrı bir dosya** — `masaustu_uygulama.py`'deki "Onaylananlar.json"
referansı sadece eski bir yorum satırı, gerçek dosya erişimi yok. Bu nedenle:
- `Onaylananlar.json` **tek process** (`mavi-admin-panel`) tarafından yazılıyor.
- `_unprocessed_cache`'in ihtiyaç duyduğu arka plan mtime-polling thread'i
  (başka bir process'in dosyayı değiştirmesi ihtimaline karşı) BU DOSYA İÇİN
  GEREKLİ DEĞİL — daha basit bir çözüm yeterli (CAVEMAN: gereksiz karmaşıklık
  eklenmeyecek).
- `src/services/data_service.py`, `mongo_service.py`, `masaustu_uygulama.py`,
  `operation_center.py` bu görevin kapsamı DIŞINDA (farklı dosya/farklı süreç).

## User Story
As a operasyon ekibi üyesi (ve otomatik onay döngüsü)
I want sevkiyat onaylama işleminin dosya boyutundan bağımsız, hızlı ve düşük
bellekli çalışmasını
So that admin panel süreci OOM/restart riskine girmeden, büyüyen onay
geçmişiyle birlikte stabil kalabilsin.

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given panel çalışıyor ve `Onaylananlar.json` diskte mevcut,
   When bir sevkiyat tekli onaylanır (`unprocessed_approve`), Then dosyanın
   TAMAMI diskten tekrar okunmaz — sadece bellekteki cache'e yeni kayıt
   eklenir ve cache diske atomik olarak yazılır; onay sonucu ve mevcut
   response formatı (`{"ok": true}`) değişmez.
2. [Critical] Given birden fazla sevkiyat aynı mesajda onaylanıyor
   (`_approve_message` / `approve_all`), When işlem çalışır, Then TÜM
   sevkiyatlar TEK bir cache güncellemesi + TEK bir disk yazımıyla eklenir
   (mevcut response formatı `{"ok": true, "count": count}` değişmez).
3. [High] Given panel ilk kez başlatılıyor (`Onaylananlar.json` cache henüz
   yüklenmemiş), When ilk onay isteği gelir, Then cache lazy/startup'ta bir
   kez diskten yüklenir (143MB'lık dosya sadece BİR KEZ, süreç ömrü boyunca
   tek seferlik okunur) ve o andan sonra sadece bellekten servis edilir.
4. [High] Given `Onaylananlar.json` diskte hiç yok (ör. temiz kurulum),
   When ilk onay gelir, Then cache boş liste olarak başlar, dosya atomik
   olarak oluşturulur, hata fırlatılmaz.
5. [Medium] Given toplu onayda bazı sevkiyatlar geçersiz lokasyon nedeniyle
   atlanıyor (mevcut `_is_valid_city` kontrolü), When `_approve_message`
   çalışır, Then SADECE geçerli olanlar cache'e/diske eklenir, atlananlar
   mevcut davranışla aynı şekilde loglanır (bu görev bu mantığı DEĞİŞTİRMİYOR,
   sadece I/O katmanını optimize ediyor).
6. [Medium] Given `approve_all` çağrılan mesajın hiç sevkiyatı kalmamış,
   When işlem çalışır, Then cache/disk'e HİÇBİR YAZMA yapılmaz (mevcut
   `"Sevkiyat yok"` hata mesajı korunur), gereksiz I/O tetiklenmez.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: tekli onay | `{"ok": true}` (200) — DEĞİŞMEDİ | Cache'e append + tek atomik disk yazımı (tüm dosya değil, cache'in serialize edilmiş hali — CAVEMAN: mevcut `_atomic_write` fonksiyonu aynen kullanılacak, sadece kaynak artık disk değil cache) | Sevkiyat listeden kalkar, "Onaylandı" (mevcut UI davranışı) | AC-1 |
| 2 | Happy path: toplu onay | `{"ok": true, "count": count}` (200) — DEĞİŞMEDİ | Tüm geçerli sevkiyatlar TEK cache güncellemesi + TEK disk yazımıyla eklenir | Mevcut UI davranışı (değişmiyor) | AC-2 |
| 3 | İlk çalıştırma / cache henüz yok | Aynı response, sadece ilk çağrıda ek bir kerelik disk okuma gecikmesi | Cache lazy-load edilir (bir kez) | Fark edilmez, normal davranış | AC-3 |
| 4 | `Onaylananlar.json` diskte yok | Aynı response | Cache `[]` başlar, dosya atomik oluşturulur | Hata yok, normal başlangıç | AC-4 |
| 5 | Kısmi başarı: toplu onayda bazı sevkiyatlar geçersiz lokasyon | Mevcut `{"ok": true, "count": count}` (sadece geçerli sayısı) — DEĞİŞMEDİ | Sadece geçerli olanlar cache/disk'e eklenir | Mevcut log/uyarı davranışı korunur | AC-5 |
| 6 | Hiçbir şey yapılamadı ama hata yok (approve_all, sevkiyat yok) | Mevcut `404 {"error": "Sevkiyat yok"}` — DEĞİŞMEDİ | Cache/disk'e HİÇBİR yazma yapılmaz | Mevcut hata mesajı | AC-6 |

Kısmi başarı: Yukarıdaki AC-5 satırında ele alındı — mevcut validasyon/atlama mantığı değişmiyor, sadece I/O katmanı optimize ediliyor.
Hiçbir şey yapılamadı ama hata da yok: AC-6'da ele alındı — boş sevkiyat listesiyle çağrılan approve_all, cache'i hiç dokunmadan mevcut hatayı döner.
Boş sonuç ↔ hata ayrımı: Bu görev kapsamında yeni bir "boş sonuç" durumu yok — mevcut `{"error": ...}` / `{"ok": true}` ayrımı zaten net ve değişmiyor.

**Silinen satırlar ve neden:**
- "Yetkisiz erişim" — bu uçlar zaten `@require_auth` dekoratörüyle korunuyor, bu görev auth katmanına dokunmuyor.
- "Dış bağımlılık hatası (ağ/DB/API)" — bu görev sadece yerel dosya I/O'sunu optimize ediyor, ağ/DB bağımlılığı yok.
- "Zaman aşımı" — yerel dosya I/O'sunda zaman aşımı kavramı yok.
- "Disk yazma hatası (disk dolu/izin yok)" — mevcut kodda da bu durum ele alınmıyor (`_atomic_write` hata durumunda exception fırlatır, Flask'ın varsayılan 500 hata işleyicisi devreye girer); bu görev mevcut hata davranışını DEĞİŞTİRMİYOR, yeni bir hata-yönetimi katmanı eklemek kapsam dışı (CAVEMAN: mevcut davranışı koru, icat etme).

## Test Strategy
Unit: 80% — cache load/save fonksiyonları (`_load_approved`, `_save_approved`,
başlangıç lazy-load mantığı), tekli/toplu onay fonksiyonlarının cache'i doğru
güncellediği.
Integration: 20% — gerçek dosya sistemi üzerinde (geçici dizin) tam
onay akışı: dosya yokken başlama, var olan dosyayı bir kez okuma, ardışık
onaylarda dosyanın tekrar tekrar okunmadığının doğrulanması (mock/spy ile
`open`/`json.load` çağrı sayısı ölçülerek).
E2E: 0% — UI değişmiyor, response formatı aynı kalıyor.

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: Süreç ömrü boyunca `Onaylananlar.json` dosyası **en fazla
1 kez** tam olarak diskten okunur (ilk erişimde) — sonraki her onay sadece
cache'e append + `_atomic_write` ile serialize (dosya boyutundan bağımsız
sabit ek maliyet, ama serialize/yazma maliyeti hâlâ O(n) — bu görev sadece
OKUMA tekrarını ortadan kaldırıyor, mevcut `_unprocessed_cache` deseniyle
aynı sınırlama).
Memory: `mavi-admin-panel` süreci, art arda 50+ onay sonrası 200MB altında
stabil kalmalı (mevcut 672MB'a kıyasla).
Diğer ölçülebilir kriterler: Test ortamında `json.load` çağrı sayısı,
N adet ardışık onay için 1'i geçmemeli (mock ile sayılabilir).

## Kapsam Dışı
- `Onaylananlar.json`'un neden 143MB'a ulaştığı (arşivleme/rotasyon eksikliği)
  bu görevde ÇÖZÜLMÜYOR — sadece mevcut boyuttaki dosyanın okuma/yazma
  pattern'i optimize ediliyor. Arşivleme ayrı bir görev olarak bırakılıyor.
- `data/onaylanmamis_ayristirilmis.json` ve `_unprocessed_cache` mekanizmasına
  DOKUNULMUYOR — zaten çalışıyor.
- `src/services/data_service.py`, `mongo_service.py`, `masaustu_uygulama.py`,
  `operation_center.py` — kod keşfinde doğrulandığı gibi bunlar FARKLI bir
  dosyayı (`onaylanan_kayitlar.json`) kullanıyor, bu görevin kapsamı dışında.
- Yazma performansı (serialize+disk yazma maliyeti, hâlâ O(n)) bu görevde
  iyileştirilmiyor — sadece tekrarlanan OKUMA maliyeti ortadan kaldırılıyor.
  Yazma maliyetinin de optimize edilmesi (ör. append-only log formatı)
  ayrı bir görev.
- Yeni bir hata-yönetimi/kullanıcı bildirim mekanizması (disk yazma
  başarısızlığı için özel UI uyarısı vb.) eklenmiyor — mevcut davranış
  korunuyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` — `unprocessed_approve` (satır ~412-467),
  `_approve_message` (satır ~471-519), yeni cache fonksiyonları
  (`_approved_cache`, `_approved_lock`, `_load_approved`, `_save_approved`)
  `_unprocessed_cache` pattern'i taklit edilerek eklenecek.

## Rollback Beklentisi
Cache sadece bellek-içi bir optimizasyon katmanı — source-of-truth her zaman
disk dosyası (`_atomic_write` zaten kısmi/bozuk yazma koruması sağlıyor).
Cache mantığında bir hata olursa (ör. süreç yeniden başlarsa), cache
kaybolur ama disk dosyası bozulmadan kalır — bir sonraki başlangıçta lazy-load
ile cache diskten yeniden kurulur, veri kaybı riski yok.

## Risks
- Cache'in bellek-içi olması, süreç çöküp yeniden başlarsa (PM2 restart) o
  ana kadar cache'e eklenmiş ama henüz diske yazılmamış hiçbir kayıt
  olmamalı — çünkü tasarım gereği her onay işleminde cache güncellemesiyle
  AYNI ANDA (senkron) `_atomic_write` çağrılacak, arka plana ertelenmeyecek
  (mevcut `_unprocessed_cache`'in `_save_unprocessed`'ı da senkron yazıyor,
  aynı garanti korunuyor).
- `_approve_lock` şu an sadece `_approve_message`'ı koruyor,
  `unprocessed_approve` (tekli onay) kilitsiz — iki eşzamanlı tekli onay
  isteği (nadir ama teorik olarak mümkün, ör. çift tıklama) cache'e yazarken
  yarışabilir. Bu görev, cache erişimini TEK bir lock (`_approved_lock`)
  altına alarak bu riski de gidermeli (mevcut `_unprocessed_lock` deseniyle
  aynı).

## Assumptions
- `Onaylananlar.json` dosyasının SADECE `admin_panel.py` tarafından
  okunup yazıldığı doğrulanmıştır (Grep ile proje genelinde arandı, tek
  eşleşme bu dosya) — bu nedenle çapraz-process senkronizasyon (mtime
  polling background thread) gerekmediği varsayılıyor.
- Panel tek bir PM2 process olarak (fork mode, cluster değil) çalışıyor —
  bu nedenle process-içi bir Python global değişkeninin tüm istekler
  arasında paylaşılabileceği varsayılıyor (mevcut `_unprocessed_cache`,
  `TOKENS`, `_status_cache` gibi global değişkenler zaten bu varsayımla
  çalışıyor).

## Unknowns
- Yok — kod keşfi ile kapsam netleştirildi.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü/persona → Operasyon ekibi (panel) + otomatik onay döngüsü (Haiku alt-ajanı tarafından yanıtlandı, doğrudan koddan da doğrulandı).
2. Happy path senaryosu → Onay isteği → cache'ten oku → append → cache+disk güncelle (Haiku alt-ajanı tarafından yanıtlandı; "disk yazma async" önerisi REDDEDİLDİ — mevcut `_unprocessed_cache` deseni senkron yazıyor, tutarlılık için aynı yaklaşım korundu).
3. Cache-disk tutarsızlığı riski → Kod keşfinde ÇÖZÜLDÜ: `Onaylananlar.json`'un tek yazıcısı `admin_panel.py`'nin kendisi, başka process yok — bu risk YOK (Haiku'nun varsaydığı çapraz-process senaryo, Grep doğrulamasıyla geçersiz kılındı).
4. Startup race condition → Cache ilk erişimde (lazy) senkron yüklenecek, ayrı bir arka plan thread'i gerekmiyor (kod keşfinde netleşti).
5. Performans/bellek hedefi → 672MB'tan 200MB altına (kullanıcı mesajından + Haiku alt-ajanı tarafından somutlaştırıldı).
6. Kapsam dışı → 143MB'a nasıl ulaşıldığı (arşivleme) ve `onaylanmamis_ayristirilmis.json` cache'i (kullanıcı mesajından, doğrudan belirtildi).
7. Bağımlılıklar/etkilenen dosyalar → SADECE `src/api/admin_panel.py` (kod keşfiyle netleşti; Haiku'nun önerdiği `data_service.py`/`mongo_service.py`/`masaustu_uygulama.py` kapsamı YANLIŞ bulundu ve reddedildi — bunlar farklı bir dosyayı, `onaylanan_kayitlar.json`'u kullanıyor).
8. Rollback beklentisi → Cache sadece optimizasyon katmanı, disk source-of-truth kalır (Haiku alt-ajanı tarafından yanıtlandı, kabul edildi).
9. Test stratejisi oranı → Unit 80/Integration 20/E2E 0 (Haiku alt-ajanı tarafından önerildi, proje tipine uygun, kabul edildi).
10. Kabul kriteri sahibi → Otomatik testler + kullanıcı onayı (bu projedeki standart, tekrar sorulmadı).
11. Bilinen riskler → `unprocessed_approve`'un şu an kilitsiz olması (kod keşfinde bulundu, Haiku'nun önerdiği çapraz-process riskinin yerine gerçek risk olarak eklendi).
12. Benchmark/başarı ölçütü → Dosya en fazla 1 kez tam okunur, sonrası O(1) okuma maliyeti (kullanıcı mesajından + Haiku alt-ajanı tarafından somutlaştırıldı).
