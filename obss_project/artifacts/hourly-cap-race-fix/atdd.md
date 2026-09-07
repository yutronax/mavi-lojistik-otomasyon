---
task_slug: hourly-cap-race-fix
jira_id: null
saga_task_id: null
priority: high
coverage_target: 85
performance_target: null
memory_target: null
test_strategy:
  unit: 70
  integration: 5
  e2e: 0
affected_modules:
  - text_gen_parser.py
---

# ATDD — hourly-cap-race-fix

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (canlı ortamda gözlemlenen bir maliyet aşımı bug'ı).

## Saga Kaynağı
Saga'ya bağlı değil — bu ortamda `project_id` bilinmiyor/yapılandırılmamış.

## Persona
Mavi Lojistik'in sistem operatörü/geliştiricisi — AI faturasını ödeyen ve sistemi işleten kişi. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## Hedef (Neden)
Saatlik AI harcama limiti (`AI_HOURLY_SPEND_CAP_TRY`, varsayılan 9 TL) bir race condition yüzünden düzgün çalışmıyor — 50 paralel worker (`ThreadPoolExecutor(max_workers=50)`) yüzünden kısa sürede gelen çok sayıda mesaj, hiçbirinin maliyeti henüz sayaca yazılmadan hepsi "limit aşılmadı" görüp işleme giriyor. Kullanıcı canlıda saatlik harcamanın ~$0.5'a (limitin ~%80 üzerine) çıktığını, 1500 istekte $2.5 harcandığını gözlemledi. Hedef: beklenmeyen bütçe aşımını önlemek. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## User Story
As a Mavi Lojistik sistem operatörü
I want saatlik AI harcama limitinin eşzamanlı isteklerde de gerçekten sınırı aşmamasını
So that beklenmedik AI faturası aşımı yaşamayayım

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given saatlik harcama 0 TL ve limit 9 TL, When 50 mesaj eşzamanlı/kısa sürede gelirse, Then her mesaj `is_hourly_cap_exceeded()`'a girdiğinde AYNI `_hourly_lock` altında hem kontrol edilir hem tahmini maliyeti (`ESTIMATED_COST_PER_CALL_TRY` sabiti) anında sayaca eklenir (rezervasyon) — toplam rezervasyon 9 TL'yi aşan noktadan sonraki mesajlar işleme girmez.
2. [Critical] Given bir mesaj için rezervasyon yapılmış (tahmini maliyet sayaca eklenmiş), When AI çağrısı BAŞARIYLA tamamlanıp gerçek maliyet (`_track_spend`) hesaplanırsa, Then sayaçtaki rezervasyon gerçek maliyetle DÜZELTİLİR (fark eklenir/çıkarılır) — sayaç asla negatife düşmez (`max(0, ...)` tabanı).
3. [High] Given bir mesaj için rezervasyon yapılmış, When AI çağrısı HATA verirse veya zaman aşımına uğrarsa, Then rezerve edilen tahmini maliyet sayaçtan GERİ ALINIR (başarısız çağrı "ceza" olarak sayılmaz).
4. [High] Given saatlik pencere değişti (yeni saat başladı), When `is_hourly_cap_exceeded()` veya `_track_spend()` çağrılırsa, Then sayaç sıfırlanır (mevcut AC-4 davranışı korunur, bu görevde değişmiyor).
5. [Medium] Given rezervasyon/düzeltme mantığında beklenmeyen bir exception oluşursa, When `is_hourly_cap_exceeded()` çağrılırsa, Then fail-open davranışı korunur — mesaj işlemi ENGELLENMEZ (mevcut satır 91-93 davranışı değişmiyor).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (limit altında, rezervasyon+gerçek maliyet düzeltmesi) | `is_hourly_cap_exceeded()` → `False`, rezervasyon sayaca eklenir | `_current_hour_cost_try` artar (tahmini), sonra gerçek maliyetle düzeltilir | Mesaj normal işlenir | AC-1, AC-2 |
| 2 | Dış bağımlılık hatası (AI API çağrısı hata verir) | `_track_spend`'e ulaşılmaz veya `cost=0` ile çağrılır | Rezervasyon sayaçtan GERİ ALINIR (`max(0, current - reserved)`) | Mesaj hata akışına düşer (mevcut davranış, bu görev değiştirmiyor) | AC-3 |
| 3 | Zaman aşımı (AI çağrısı timeout) | Dış bağımlılık hatasıyla aynı: rezervasyon geri alınır | Sayaç düzeltilir | Mesaj hata akışına düşer (mevcut davranış) | AC-3 |
| 4 | Hiçbir şey yapılamadı ama hata yok (limit dolu, mesaj ertelenir) | `is_hourly_cap_exceeded()` → `True` | Rezervasyon yapılmaz (limit zaten dolu) | Mesaj postpone edilir, mark edilmez (mevcut davranış korunur) | — |
| 5 | Rezervasyon/düzeltme mantığında beklenmeyen hata | Exception yakalanır, `False` döner (fail-open) | Sayaç durumu değişmeyebilir | Mesaj normal işlenmeye devam eder (limit yokmuş gibi) | AC-5 |

Satır "Girdi geçersiz/eksik", "Kaynak yok", "Yetkisiz erişim", "Kısmi başarı" silindi: bu dahili, kullanıcı girdisi almayan bir fonksiyon (Sonnet 5 alt-ajanı gerekçesi) — kısmi başarı da uygulanmıyor çünkü tek bir AI çağrısı ya tam başarılı ya değil, ara bir durum yok.

Kısmi başarı: Uygulanmıyor (bkz. yukarı).
Hiçbir şey yapılamadı ama hata da yok: Limit doluyken mesaj ertelenmesi — mevcut davranış (postpone, mark etmeden) korunuyor, bu görev sadece kontrolün atomikliğini düzeltiyor.
Boş sonuç ↔ hata ayrımı: N/A — bu fonksiyon boolean döner, "veri yok"/"hata" ayrımı bağlamı yok.

## Test Strategy
Unit: 70% — rezervasyon/düzeltme/geri-alma mantığının izole testleri (`text_gen_parser.py`'deki fonksiyonlar).
Integration: 5% — `is_hourly_cap_exceeded()` + `_track_spend()` akışının uçtan uca (gerçek `_hourly_lock` ile) simülasyonu.
E2E: 0% — bu saf bir concurrency/threading bug'ı, UI/tarayıcı testi gerektirmiyor. (Sonnet 5 alt-ajanı gerekçesi)

Ayrıca **thread-safety testleri** (unit'in %25'lik kısmı, `tests/test_dedup_active_ids_fix.py`'deki desenle) — gerçek `ThreadPoolExecutor` veya `threading.Thread` ile 50 eşzamanlı çağrı simüle edilip toplam rezervasyonun limiti öngörülebilir bir payla aştığı doğrulanmalı.

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: yok
Memory: yok
Diğer ölçülebilir kriterler: 50 eşzamanlı istekle simüle edilen bir testte, saatlik toplam (rezerve + gerçek) maliyet, limiti en fazla **tek bir rezervasyon birimi (`ESTIMATED_COST_PER_CALL_TRY`) kadar** aşabilir — mevcut ~2x limit aşımı yerine sabit, öngörülebilir ve küçük bir tolerans payı. (Sonnet 5 alt-ajanı gerekçesi: somut yüzdeye bağlamak spekülatif olur, "tek rezervasyon birimi" ölçülebilir ve test edilebilir bir hedef)

## Kapsam Dışı
- `MAX_WORKERS_DEFAULT` (50) değiştirilmeyecek.
- `ThreadPoolExecutor` mimarisi / `veri_cekici_ayristirici.py`'nin genel akışı değişmeyecek — çağrı arayüzü (`is_hourly_cap_exceeded()`'ın imzası) aynı kalacağı için bu dosyaya dokunulması gerekmiyor.
- `AI_HOURLY_SPEND_CAP_TRY` değerinin kendisi (9 TL) bu görevde değiştirilmeyecek — ayrı bir konfigürasyon kararı (kullanıcı daha önce "150 TL/gün, 22-08 kapalıysa saat başı ~10.71 TL" hesaplaması yapmıştı, ama bu görev sadece mekanizmanın DOĞRU çalışmasını hedefliyor, değeri değiştirmiyor).
- Farklı bir rezervasyon stratejisi (geçmiş N çağrının dinamik ortalaması) — CAVEMAN: sabit bir `ESTIMATED_COST_PER_CALL_TRY` sabiti kullanılacak, ekstra state eklenmeyecek.

## Etkilenen Dosyalar/Modüller (bilinen)
- `text_gen_parser.py` (`is_hourly_cap_exceeded()`, `_track_spend()`, ilgili global state)
- Yeni: `tests/test_hourly_cap_race_condition.py`

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu worktree'nin git kökü proje klasörüyle aynı görünüyor, ancak daha geniş bir dizin/devasa git geçmişi olup olmadığı ayrıca doğrulanmadı. Aramalar `text_gen_parser.py` ve `tests/` ile sınırlı tutulmalı.

## Rollback Beklentisi
Fail-open korunmalı: rezervasyon/düzeltme mantığında beklenmeyen bir hata olursa mesaj işlemi ENGELLENMEMELİ — mevcut `is_hourly_cap_exceeded()`'ın satır 91-93'teki fail-open davranışı (hata durumunda `False` dönme, limit yokmuş gibi devam) aynen korunacak. (Sonnet 5 alt-ajanı gerekçesi)

## Risks
- Rezervasyon tutarı (`ESTIMATED_COST_PER_CALL_TRY`) gerçek ortalama maliyetten çok farklıysa (örn. çok düşük tahmin edilirse), race window küçülür ama tamamen kapanmaz — bu görev "aşımı öngörülebilir küçük bir paya indirmeyi" hedefliyor, "sıfır aşım" garantisi vermiyor (gerçek maliyet API cevabı gelmeden bilinemez, bu fiziksel bir sınır).
- `_track_spend()`'in başarısız çağrılarda rezervasyonu geri alması için, çağıran kodun (muhtemelen `veri_cekici_ayristirici.py` içindeki AI çağrı wrapper'ı) hata durumunda da bir "geri alma" sinyali göndermesi gerekebilir — plan.md aşamasında bu entegrasyon noktası netleştirilmeli (atdd.md'nin "Bağımlılıklar" bölümü şu an "veri_cekici_ayristirici.py'ye dokunulmaz" diyor, ama hata-durumunda-geri-alma akışı bunu gerektirebilir, bu bir açık soru).

## Assumptions
- `ESTIMATED_COST_PER_CALL_TRY` sabit bir değer olarak, mevcut model fiyatlandırmasından (DeepSeek/Groq ortalaması) makul bir "ortalama mesaj" tahminiyle belirlenecek — kullanıcı tam bir sayı onaylamadı, `plan`/`code-copilot` aşamasında mevcut `_track_spend()`'teki fiyat sabitlerinden türetilecek.
- Başarısız/timeout AI çağrılarının rezervasyonu geri alma sinyalini nasıl göndereceği (bir `except` bloğu mu, `finally` mi) `plan` aşamasında netleştirilecek.

## Unknowns
- Rezervasyon geri alma akışının `veri_cekici_ayristirici.py`'ye hiç dokunmadan (sadece `text_gen_parser.py` içinde) yapılıp yapılamayacağı — AI çağrısını yapan asıl fonksiyonun `text_gen_parser.py` içinde mi yoksa `veri_cekici_ayristirici.py`'de mi olduğu `plan` aşamasında doğrulanmalı.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü / persona → Sistem operatörü/geliştiricisi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
2. Ana hedef / neden → Beklenmeyen bütçe aşımını önlemek (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Happy path → Rezervasyon 9 TL'yi aşana kadar mesajlar geçer, sonrası ertelenir (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. Edge case (rezervasyon/gerçek fark) → Negatife düşmez, max(0,...) tabanı (Sonnet 5 alt-ajanı tarafından yanıtlandı)
5. Edge case (aynı anda okuma/yazma) → Mevcut _hourly_lock yeterli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Tahmini maliyet hesaplama → Sabit ESTIMATED_COST_PER_CALL_TRY sabiti (Sonnet 5 alt-ajanı tarafından yanıtlandı)
7. Davranış sözleşmesi tablosu → yukarıdaki tabloya işlendi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
8. Başarı ölçütü → tek rezervasyon birimi kadar tolerans (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Kapsam dışı → MAX_WORKERS_DEFAULT, ThreadPoolExecutor mimarisi, cap değeri değişmiyor (Sonnet 5 alt-ajanı tarafından yanıtlandı)
10. Bağımlılıklar → sadece text_gen_parser.py + yeni test dosyası (Sonnet 5 alt-ajanı tarafından yanıtlandı)
11. Test stratejisi → %70 unit / %5 integration / %0 e2e + thread-safety testleri (Sonnet 5 alt-ajanı tarafından yanıtlandı)
12. Rollback beklentisi → fail-open korunmalı (Sonnet 5 alt-ajanı tarafından yanıtlandı)
