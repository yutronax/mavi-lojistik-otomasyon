---
task_slug: onaylananlar-jsonl-append
jira_id: null
saga_task_id: null
priority: critical
coverage_target: 85
performance_target: "onay işlemi O(1) bellek/CPU (dosya boyutundan TAMAMEN bağımsız — cache dahil değil)"
memory_target: "mavi-admin-panel süreci, 149MB+/31K+ kayıtlı gerçek dosya üzerinde bile art arda 50+ onay sonrası 200MB altında stabil"
test_strategy:
  unit: 70
  integration: 30
  e2e: 0
affected_modules:
  - src/api/admin_panel.py
  - scripts/migrate_onaylananlar_to_jsonl.py (yeni)
---

# ATDD — onaylananlar-jsonl-append

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (production incident'ından doğdu, postmortem-bilgili).

## POSTMORTEM — Bu görev neden var (ÖNCEKİ BAŞARISIZ DENEMENİN TAM AÇIKLAMASI)
Önceki görev (`onaylananlar-cache-fix`, commit `a5bc519`, **revert edildi** →
`2943b15`) `data/Onaylananlar.json`'un (o zaman 143MB tahmin edilmişti,
gerçekte **149MB, 31.403 kayıt**) her onayda tam okunup tam yazılması
sorununu, TÜM listeyi bellekte bir Python cache olarak TUTARAK çözmeye
çalıştı. Bu, dev ortamında (`data/Onaylananlar.json` sadece 244KB'lık bir
test kopyasıydı) sorunsuz görünüyordu ve tüm testler geçiyordu. Ama VPS'e
deploy edildiğinde, GERÇEK 149MB'lık dosya:
- Python'a `json.load()` ile yüklendiğinde **969MB**'a şişiyor (ölçüldü,
  VPS'te doğrudan test edildi) — JSON metninin Python obje modelindeki
  (dict/string overhead) ~6.5 kat büyümesi yüzünden.
- `json.dumps(..., indent=2)` ile yeniden serialize edildiğinde toplam
  **~1107MB**'a çıkıyor.
- Production'da süreç **1235MB**'a fırlayıp PM2'nin 700MB `max_memory_restart`
  limitini aşarak OOM-kill edildi, ~7 dakikada bir tekrarlayan bir çökme
  döngüsüne girdi (önceki 672MB'lık sorundan DAHA KÖTÜ).
- Commit revert edilip VPS'e deploy edilerek stabilite geri getirildi.

**Çıkarılan ders — bu görevin ZORUNLU kısıtı:** Herhangi bir çözüm,
`Onaylananlar.json`/`Onaylananlar.jsonl`'ın TAM İÇERİĞİNİ (149MB'lık gerçek
dosya, gelecekte daha da büyüyecek) HİÇBİR ŞEKİLDE (ne cache olarak, ne
geçici bir değişken olarak) tam olarak BELLEĞE YÜKLEMEMELİDİR — ne okuma
ne de yazma sırasında. Bu görevin verify adımı, gerçek boyutta (en az
30.000+ kayıt, birkaç on MB) SENTETİK bir dosya üzerinde bellek profilini
ÖLÇMEK ZORUNDADIR — küçük/geçici test dosyalarıyla "testler geçti" demek
YETERLİ DEĞİLDİR (önceki görevin tam olarak bu yüzden başarısız olduğu
kanıtlandı).

## Persona
Panel'i kullanan operasyon ekibi (web/mobil arayüzden tekli/toplu onay
yapan) ve sunucu-taraflı otomatik onay döngüsü (`_auto_approve_loop`, her
3 saniyede bir tetiklenebilir).

## Hedef (Neden)
Onay işleminin, `Onaylananlar` veri dosyasının BOYUTUNDAN TAMAMEN BAĞIMSIZ,
sabit (O(1)) bellek/CPU maliyetiyle çalışmasını sağlamak — dosya ister
149MB ister 1.5GB olsun, tek bir onay işlemi aynı, küçük, sabit kaynak
kullanmalı. Bu, hem orijinal sorunu (tam dosya oku/yaz) hem de önceki
başarısız denemenin yarattığı YENİ sorunu (tam dosyayı bellekte cache'leme)
kökünden çözer.

## User Story
As a operasyon ekibi üyesi (ve otomatik onay döngüsü)
I want sevkiyat onaylama işleminin, onay geçmişi dosyasının boyutundan
bağımsız, sabit ve düşük kaynaklı çalışmasını
So that admin panel süreci, dosya ne kadar büyürse büyüsün asla OOM/restart
riskine girmesin.

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `Onaylananlar.jsonl` dosyası (JSON Lines formatı, her
   satır bir sevkiyat kaydı) mevcut ve BÜYÜK (30.000+ satır/birkaç on MB),
   When bir sevkiyat tekli onaylanır, Then dosyanın MEVCUT İÇERİĞİ HİÇ
   OKUNMAZ/BELLEĞE YÜKLENMEZ — sadece yeni kayıt dosyanın SONUNA eklenir
   (append). Response formatı `{"ok": true}` değişmez.
2. [Critical] Given birden fazla sevkiyat aynı mesajda onaylanıyor
   (`_approve_message`/`approve_all`), When işlem çalışır, Then TÜM geçerli
   sevkiyatlar TEK bir dosya açma/yazma işleminde (append) dosyanın sonuna
   eklenir — mevcut içerik yine hiç okunmaz. Response formatı
   `{"ok": true, "count": count}` değişmez.
3. [Critical] Given süreç bellek profili ölçülüyor, When 30.000+ satırlık
   BÜYÜK bir `Onaylananlar.jsonl` üzerine ART ARDA 50 onay yapılıyor, Then
   Python süreç belleği (RSS) dosyanın BAŞLANGIÇ boyutundan (ör. 50MB+)
   BAĞIMSIZ olarak sabit kalır — sadece birkaç MB artış (append tamponu),
   asla dosya boyutuyla orantılı büyümez. Bu, sentetik büyük dosyayla
   `resource.getrusage`/`tracemalloc` ile ÖLÇÜLECEK, varsayılmayacak.
4. [High] Given `Onaylananlar.jsonl` diskte hiç yok (ör. migration henüz
   çalıştırılmamış veya temiz kurulum), When ilk onay gelir, Then dosya
   `'a'` (append) modunda otomatik oluşturulur, hata fırlatılmaz.
5. [High] Given eski `Onaylananlar.json` (149MB, tek JSON dizisi, 31.403
   kayıt) production'da mevcut, When migration script'i (bu görevin bir
   parçası, `scripts/migrate_onaylananlar_to_jsonl.py`) manuel olarak
   çalıştırılır, Then TÜM 31.403 kayıt, veri kaybı olmadan
   `Onaylananlar.jsonl`'a (her satır bir kayıt) dönüştürülür; orijinal
   `Onaylananlar.json` SİLİNMEZ (yedek olarak kalır).
6. [Medium] Given toplu onayda bazı sevkiyatlar geçersiz lokasyon nedeniyle
   atlanıyor (mevcut `_is_valid_city` kontrolü), When `_approve_message`
   çalışır, Then SADECE geçerli olanlar dosyaya append edilir, atlananlar
   mevcut davranışla aynı şekilde loglanır.
7. [Medium] Given `approve_all` çağrılan mesajın hiç sevkiyatı kalmamış
   VEYA tüm sevkiyatlar geçersiz lokasyon nedeniyle atlanmış, When işlem
   çalışır, Then dosyaya HİÇBİR satır append edilmez.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: tekli onay | `{"ok": true}` (200) — DEĞİŞMEDİ | Dosyanın SONUNA 1 satır (1 JSON kaydı + `\n`) append edilir, mevcut içerik OKUNMAZ | Sevkiyat listeden kalkar | AC-1 |
| 2 | Happy path: toplu onay | `{"ok": true, "count": count}` (200) — DEĞİŞMEDİ | Tüm geçerli sevkiyatlar TEK bir append çağrısında (N satır, tek dosya açma) eklenir | Mevcut UI davranışı | AC-2 |
| 3 | Bellek profili (büyük dosya) | N/A (fonksiyonel değil, ölçüm) | Süreç belleği dosya boyutundan bağımsız kalır | N/A | AC-3 |
| 4 | Dosya yok (ilk kurulum) | Aynı response | Dosya `'a'` modunda otomatik oluşturulur | Hata yok | AC-4 |
| 5 | Migration (manuel, bir kerelik) | Script çıktısı: "31403 kayıt taşındı" | Yeni `.jsonl` oluşur, eski `.json` SİLİNMEZ | Kullanıcı script çıktısını görür | AC-5 |
| 6 | Kısmi başarı: geçersiz lokasyon | Mevcut `{"ok": true, "count": count}` (sadece geçerli sayısı) — DEĞİŞMEDİ | Sadece geçerli olanlar append edilir | Mevcut log davranışı | AC-6 |
| 7 | Hiçbir şey yapılamadı, hata yok | Mevcut `404 {"error": "Sevkiyat yok"}` — DEĞİŞMEDİ | Dosyaya HİÇBİR satır append edilmez | Mevcut hata mesajı | AC-7 |

Kısmi başarı: AC-6'da ele alındı.
Hiçbir şey yapılamadı ama hata da yok: AC-7'de ele alındı.
Boş sonuç ↔ hata ayrımı: Bu görev kapsamında yeni bir durum yok, mevcut ayrım korunuyor.

**Silinen satırlar ve neden:** Önceki görevle aynı gerekçelerle "Yetkisiz
erişim" (zaten `@require_auth` korumalı), "Dış bağımlılık hatası"
(yerel dosya I/O, ağ/DB yok), "Zaman aşımı" (yerel dosya I/O'da yok),
"Disk yazma hatası" (mevcut davranış değişmiyor, `_atomic_write`
kullanılmıyor artık ama append de kendi başına atomik bir birincil işlem
değil — bu, Risks bölümünde AYRICA ele alınıyor, silinmedi).

## Test Strategy
Unit: 70% — append fonksiyonunun mantığı (dosya var/yok, tek/toplu kayıt).
Integration: 30% — **GERÇEK BOYUTTA SENTETİK DOSYA ÜZERİNDE** bellek
profili testi (AC-3, bu görevin EN KRİTİK testi) + migration script'inin
gerçek bir örnek `Onaylananlar.json` üzerinde uçtan uca doğrulanması.
E2E: 0% — UI değişmiyor.

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: Append işlemi O(1) — dosya boyutundan BAĞIMSIZ sabit
maliyet. **ZORUNLU doğrulama**: en az 30.000 satır/30MB+ sentetik
`Onaylananlar.jsonl` oluşturup üzerine 50 onay yapıldıktan sonra RSS artışı
birkaç MB'ı (ör. <20MB) geçmemeli — `resource.getrusage(RUSAGE_SELF).ru_maxrss`
ile ÖLÇÜLECEK.
Memory: `mavi-admin-panel` süreci, gerçek 149MB'lık (veya daha büyük)
dosya üzerinde bile 200MB altında stabil kalmalı.
Diğer ölçülebilir kriterler: Migration script'i 31.403 kaydı kayıpsız
taşımalı (satır sayısı = orijinal kayıt sayısı, doğrulanacak).

## Kapsam Dışı
- `Onaylananlar.jsonl`'dan veri OKUYAN/listeleyen bir endpoint eklemek —
  şu an admin_panel.py'de bu dosyayı geri okuyup kullanıcıya gösteren
  hiçbir kod yok (grep ile doğrulandı, sadece yazılıyor). İleride böyle bir
  ihtiyaç doğarsa (ör. "onaylanan sevkiyatları listele" sayfası), o zaman
  STREAMING bir okuma stratejisi (tail -n benzeri, TAM dosyayı yüklemeden)
  AYRI bir görev olarak ele alınmalı — bu görev sadece YAZMA tarafını
  çözüyor.
- Eski `Onaylananlar.json`'un silinmesi/arşivlenmesi — migration script'i
  onu SİLMEZ, kullanıcı manuel karar verip silecek (veri kaybı riskini
  otomatikleştirmek CAVEMAN'a aykırı, geri dönüşü olmayan bir işlem).
- `data_service.py`/`mongo_service.py`/`masaustu_uygulama.py`/
  `operation_center.py` — önceki görevde olduğu gibi farklı bir dosyayı
  (`onaylanan_kayitlar.json`) kullanıyorlar, kapsam dışı.
- `ai_spend_history.json` gibi benzer şekilde büyüyebilecek diğer dosyalar
  — bu görev SADECE `Onaylananlar.json`/`.jsonl`'ı hedefliyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` — `unprocessed_approve`, `_approve_message`,
  `APPROVED_PATH` (yeni: `Onaylananlar.jsonl`'a işaret edecek).
- `scripts/migrate_onaylananlar_to_jsonl.py` (YENİ) — bir kerelik,
  manuel çalıştırılan migration script'i.

## Rollback Beklentisi
Migration script'i eski `Onaylananlar.json`'u SİLMEDİĞİ için, JSONL
formatında bir sorun çıkarsa eski dosya hâlâ diskte durur — kod
`APPROVED_PATH`'i eski dosyaya geri işaret edecek şekilde revert edilebilir
(git revert, önceki görevde yapıldığı gibi), veri kaybı riski yok.
Append işleminin kendisi başarısız olursa (ör. disk dolu), mevcut kod gibi
exception'ı yutmuyor — Flask'ın varsayılan 500 hata işleyicisi devreye
girer (mevcut davranışla tutarlı, değişmiyor).

## Risks
- **Append'in atomikliği**: POSIX sistemlerde (VPS Ubuntu) `O_APPEND` ile
  açılan bir dosyaya PIPE_BUF (genelde 4096 byte) altındaki TEK bir
  `write()` syscall'ı atomiktir — ama Python'un buffered `open(path, 'a')`
  + `.write(str)` çağrısı, string büyükse (ör. çok büyük bir sevkiyat
  kaydı veya kalabalık bir toplu onay) BİRDEN FAZLA syscall'a bölünebilir,
  bu da eşzamanlı yazımlar arasında satırların İÇ İÇE GEÇMESİ (interleaving)
  riskini taşır. **Bu görev bunu ele almalı**: ya tüm append'leri TEK bir
  paylaşılan lock (`_approve_lock` veya yeni bir `_approved_write_lock`)
  altına almalı, ya da her satırın makul boyutta kalacağını (tipik bir
  sevkiyat kaydı birkaç KB, PIPE_BUF'ın altında) kabul edip düşük öncelikli
  bir sınırlama olarak not düşmeli — plan aşamasında karara bağlanacak.
- **Migration sırasında bellek**: Migration script'i, mevcut 149MB'lık
  dosyayı BİR KEZ `json.load()` ile okuyacak (~970MB'a şişecek) — bu,
  standalone bir script olarak PM2'nin 700MB limitinin DIŞINDA
  çalıştırılacağı için sorun değil, ama VPS'in toplam RAM'i (~1.9GB) ile
  `mavi-lojistik-server`'ın (~600MB) aynı anda çalışıyor olması dikkate
  alınmalı — kullanıcıya migration'ı düşük yük anında çalıştırması
  önerilecek.
- **Eski görevin tam olarak bu yüzden başarısız olduğu unutulmamalı**:
  Her PR/verify adımı, KÜÇÜK/geçici test dosyalarıyla "çalışıyor" demeyi
  YETERSİZ SAYMALI — AC-3'ün büyük-dosya bellek testi ZORUNLU, atlanamaz.

## Assumptions
- `Onaylananlar.jsonl`'dan hiçbir kod şu an geri okuma yapmıyor (grep ile
  doğrulandı) — bu nedenle formatı JSON dizisinden JSON Lines'a değiştirmek
  güvenli, başka hiçbir tüketiciyi bozmuyor.
- Migration script'i kullanıcı tarafından MANUEL çalıştırılacak (admin_panel.py
  başlangıcında OTOMATİK tetiklenmeyecek) — otomatik tetiklemek, tam da
  önceki incident'a yol açan "büyük dosyayı sürecin kendi bellek
  bütçesinde işleme" hatasını tekrarlar.

## Unknowns
- Yok — postmortem ile kapsam netleşti.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı isteği → "append-only log yaklaşımıyla düzeltmeyi tekrar
   tasarla" (kullanıcı mesajından, birebir).
2. Format seçimi (JSON Lines) → Ben önerdim: mevcut `Onaylananlar.json`'un
   tek bir JSON dizisi olması, her yazımda tam yeniden serialize
   gerektiriyordu; JSON Lines (her satır bağımsız bir JSON objesi) saf
   append ile genişleyebiliyor, bu da O(1) yazma maliyeti sağlıyor —
   endüstride yaygın, log-tipi veri için standart bir format.
3. Migration script'inin bellek maliyeti → Kabul edilebilir risk olarak
   işaretlendi (kullanıcı mesajından türetilen kapsam: "tekrar tasarla",
   bir kerelik migration'ın kendisi hedef DEĞİL, sürekli/tekrarlayan onay
   yolunun maliyeti hedef).
4. Eski dosyanın silinip silinmeyeceği → Silinmeyecek (CAVEMAN + veri
   güvenliği: geri dönüşü olmayan işlemler otomatikleştirilmez).
