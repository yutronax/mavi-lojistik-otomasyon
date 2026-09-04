---
task_slug: saatlik-harcama-ust-limit
jira_id: null
saga_task_id: null
priority: high
coverage_target: 85
performance_target: "O(1) kontrol (dosya okuma yok, bellek içi sayaç)"
memory_target: null
test_strategy:
  unit: 85
  integration: 15
  e2e: 0
affected_modules:
  - text_gen_parser.py
  - src/parsers/veri_cekici_ayristirici.py
---

# ATDD — saatlik-harcama-ust-limit

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga bağlantısı bu oturumda kurulamadı
(tekrarlayan MCP timeout) — `saga_task_id: null`.

## Persona
Sistem operatörü (kullanıcı) — günlük 80 TL bütçesini `deepseek-maliyet-
dusurme-stage-birlestir-junk-filtre` görevindeki optimizasyonlarla zaten
düşürdü, ama öngörülemeyen bir trafik patlamasına karşı ek bir güvenlik
ağı istiyor.

## Hedef (Neden)
Bu oturumda önce Stage1+Stage2 birleştirme ve junk-filtre ile mesaj başına
DeepSeek çağrısı ~2'den ~1'e indirildi (ayrı görev, commit edildi,
maliyetin ~%40-50 düştüğü projeksiyonu var ama DeepSeek bakiyesi 0
olduğu için canlı doğrulanamadı). Bu, BİRİNCİL maliyet kontrolü. Kullanıcı
şimdi buna EK olarak, "throttle/pacing değil, sadece bir güvenlik ağı"
istiyor: saat başı harcama beklenmedik şekilde patlarsa (örn. anormal
mesaj hacmi, retry fırtınası), o saatin geri kalanında yeni mesajların
kuyruğa girmesini durdurup bütçenin erken tükenmesini önlemek.

## User Story
As a sistem operatörü
I want saatlik AI (DeepSeek+Groq toplamı) harcaması ayarlanabilir bir
eşiği aşınca yeni mesajların işlenmeye alınmasını geçici olarak durdurmayı
So that öngörülemeyen bir trafik patlaması günlük bütçemi saatler
içinde tüketmesin, ama normal trafikte hiçbir davranış değişikliği
olmasın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given saat başı harcama eşiğin ALTINDA, When yeni bir mesaj
   `add_to_processing_queue()`'ya gelir, Then mevcut davranış AYNEN
   sürmeli — hiçbir yeni kod yolu tetiklenmemeli, mesaj normal işlenmeli.
2. [Critical] Given saat başı toplam harcama (DeepSeek+Groq) ayarlanabilir
   `AI_HOURLY_SPEND_CAP_TRY` eşiğini (varsayılan 9 TL/saat — günlük 80 TL
   / ~14 aktif saat ≈ 5.7 TL/saat ortalamasının üstünde, gerçek bir
   patlamayı yakalayacak ama normal dalgalanmada tetiklenmeyecek bir marj)
   AŞMIŞ, When yeni bir mesaj gelir, Then bu mesaj kuyruğa EKLENMEMELİ,
   ayrı bir "ertelenmiş" listede tutulmalı, WARN seviyesinde loglanmalı.
3. [Critical] Given limit aşılmışken KUYRUKTA ZATEN OLAN veya
   `ThreadPoolExecutor`'da işlenmekte olan mesajlar, When limit kontrolü
   çalışır, Then bu mesajlar DURDURULMAMALI — sadece YENİ mesajların
   kuyruğa eklenmesi engellenir, mevcut işlem akışı kesilmez.
4. [High] Given saat değişimi (örn. 14:59 → 15:00), When yeni saat dilimi
   başlar, Then önceki saatin harcaması pencere dışında kalmalı VE
   ertelenmiş mesajlar OTOMATİK olarak kuyruğa aktarılmalı — manuel
   müdahale gerekmeden.
5. [High] Given `ai_spend_history.json` dosyası bozuk/okunamıyor VEYA
   bellek içi sayaç ilklendirilememiş, When limit kontrolü çalışır, Then
   FAIL-OPEN davranmalı (limit yokmuş gibi mesaj işlemeye devam etmeli) —
   bir dosya/parse hatası yüzünden TÜM sistem durmamalı; hata ERROR
   seviyesinde loglanmalı.
6. [Medium] Given saat başı harcama TAM eşikte (== eşik, eşiği AŞMAMIŞ),
   When kontrol çalışır, Then mesaj ENGELLENMEMELİ (`>` kullanılmalı,
   `>=` değil) — sadece eşiği GERÇEKTEN geçen andan itibaren erteleme
   başlamalı.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: eşik altında | Mesaj normal işlenir | Yok, mevcut davranış | Değişiklik yok | AC-1 |
| 2 | Girdi geçersiz/eksik: `ai_spend_history.json` bozuk/eksik | Fail-open: limit yokmuş gibi devam | ERROR log | Mesajlar normal işlenmeye devam eder | AC-5 |
| 3 | Kısmi başarı: harcama TAM eşikte | Mesaj İŞLENİR (engellenmez) | Yok | Değişiklik yok | AC-6 |
| 4 | Hiçbir şey yapılamadı ama hata yok: limit aşıldı, mesaj ertelendi | Mesaj kuyruğa eklenmez, ayrı listeye alınır | WARN log ("saatlik limit aşıldı, N mesaj ertelendi") | Panelde görünmez (kapsam dışı UI), loglarda iz bırakır | AC-2 |
| 5 | Devam eden işlem: limit aşılırken zaten kuyrukta/işlenmekte olan mesajlar | Etkilenmez, normal tamamlanır | Yok | Değişiklik yok | AC-3 |
| 6 | Saat değişimi | Pencere kayar, ertelenmiş mesajlar otomatik kuyruğa döner | Log: "yeni saat dilimi, N ertelenmiş mesaj kuyruğa alındı" | Ertelenen mesajlar gecikmeli işlenir | AC-4 |

Kaynak yok / Dış bağımlılık hatası: N/A — bu görevde dış bir servis
bağımlılığı yok, sadece yerel dosya (restart-kurtarma için) + bellek içi
sayaç kullanılıyor, bu satırlar silindi.

Boş sonuç ↔ hata ayrımı: "Limit aşılmadı, mesaj normal" (boş/sessiz
sonuç) ile "limit kontrolü BAŞARISIZ oldu, fail-open'a düştük" (hata)
AYRI loglanmalı — biri hiç log üretmez (happy path), diğeri ERROR log
üretir; ikisi de mesajın işlenmesine izin verir ama NEDENİ farklı ve
izlenebilir olmalı.

## Test Strategy
Unit: 85% — `_hourly_spend_exceeded()` (veya benzer) fonksiyonunun eşik
altı/üstü/tam sınır senaryoları, saat penceresi geçişi hesaplaması, bozuk
veri karşısında fail-open davranışı — tamamen deterministik saf mantık.
Integration: 15% — `add_to_processing_queue()`'nun bu kontrolü gerçekten
çağırdığını, limit aşılınca mesajın kuyruğa GİRMEDİĞİNİ, limit altına
dönünce (yeni saat) ertelenen mesajın kuyruğa girdiğini doğrulayan test.
E2E: 0% — gerçek API/gerçek saat geçişi test edilemez/gereksiz, DeepSeek
bakiyesi zaten 0.

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: O(1) kontrol — her mesaj kontrolünde `ai_spend_
history.json`'un TAMAMI okunmamalı (2045+ kayıtlı, sürekli büyüyen bir
dosya — performans riski). Worker process içinde bellek içi bir sayaç
(`current_hour_start`, `current_hour_total_cost_try`) tutulmalı, dosya
SADECE process başlangıcında (restart-kurtarma) bir kez okunmalı.
Memory: yok
Diğer ölçülebilir kriterler:
- Mock'lu testlerle: eşik altı → işlenir, eşik üstü → ertelenir, tam
  eşik → işlenir, saat geçişi → pencere doğru kayar, bozuk veri →
  fail-open, hepsi test edilmeli.

## Kapsam Dışı
- Admin panelde görsel gösterge/uyarı (ayrı bir görev olarak önerilir).
- Günlük/haftalık toplam limit — SADECE saatlik.
- Model/retry sırası değişikliği.
- Mevcut `_track_spend`'in maliyet formülü (cache-hit/miss fiyatlandırma)
  düzeltmesi — ayrı, çözülmemiş bir konu, bu görev sadece MEVCUT
  (yanlış olsa bile) `cost_try` değerlerini toplayarak eşikle karşılaştırır.
- Throttle/pacing (istekleri yavaşlatma) — kullanıcı açıkça "throttle
  değil, sadece güvenlik ağı" dedi.

## Etkilenen Dosyalar/Modüller (bilinen)
- `text_gen_parser.py` (`_track_spend`'in yanına veya yakınına yeni bir
  bellek-içi sayaç güncelleme çağrısı)
- `src/parsers/veri_cekici_ayristirici.py` (`add_to_processing_queue()`'ya
  yeni bir `_hourly_spend_exceeded()` kontrolü — junk-filtre'nin
  eklendiği noktaya yakın, aynı "kuyruğa girmeden önceki son kapı"
  mantığı)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımından önce `git rev-parse --show-toplevel` ile
kontrol edilecek.

## Rollback Beklentisi
Düz kod değişikliği + yeni bir env değişkeni (`AI_HOURLY_SPEND_CAP_TRY`,
varsayılan devredeyken mevcut davranışı bozmaz). `git revert` yeterli.

## Risks
- Bellek-içi sayaç, uygulama YENİDEN BAŞLATILDIĞINDA sıfırlanır — restart
  sonrası `ai_spend_history.json`'dan o saatin GERÇEK toplamını
  kurtarmak (restore) gerekiyor, aksi halde restart sonrası limit
  yanlışlıkla "sıfırdan" başlar (kısa süreliğine limitsiz kalır — kabul
  edilebilir küçük bir risk, ama `plan` adımında ele alınmalı).
- Birden fazla worker thread (`max_workers=50`) aynı anda bu sayacı
  güncelleyebilir — thread-safety (lock) gerekebilir, `plan` adımında
  netleştirilmeli.

## Assumptions
- Limit, DeepSeek VE Groq harcamasının TOPLAMINI kapsıyor ("AI harcaması"
  ifadesi ikisini de içeriyor gibi okunuyor) — kullanıcı bunu açıkça
  onaylamadı, varsayım olarak işaretleniyor.
- Varsayılan eşik (9 TL/saat) bir öneri — kullanıcı onaylamadan
  kesinleşmiyor, `plan`/hard-stop onayında teyit edilmeli.

## Unknowns
- Ertelenmiş mesajların tutulacağı yapı (ayrı bir dosya mı, bellek içi
  bir liste mi) — `plan` adımında mevcut kuyruk/veri yapılarına bakılarak
  netleştirilecek; bellek içi liste daha basit ama process restart'ında
  kaybolur (junk-filtre'nin de benzer bir "kaybolma" riski yok çünkü o
  mesajı tamamen elerken, bu ERTELİYOR — kaybolmaması daha önemli).

## Sorular ve Cevaplar (ham kayıt)
1. Happy path → eşik altında mevcut davranış aynen sürer (Sonnet 5
   alt-ajanı tarafından yanıtlandı)
2. Eşik değeri → `AI_HOURLY_SPEND_CAP_TRY`, varsayılan 9 TL/saat, env
   değişkeni olarak ayarlanabilir (Sonnet 5 alt-ajanı tarafından
   yanıtlandı)
3. Edge case'ler → `>` kullan (`>=` değil), saat geçişinde pencere
   otomatik kayar, bozuk veri fail-open (Sonnet 5 alt-ajanı tarafından
   yanıtlandı, gerekçeli: fail-closed'ın riski sınırsız iş durması,
   fail-open'ın riski sınırlı fazla harcama)
4. Davranış sözleşmesi/kısmi başarı → yumuşak yaklaşım, sadece yeni
   mesaj eklemeyi durdur, mevcut işlemi kesme (Sonnet 5 alt-ajanı
   tarafından yanıtlandı)
5. Kullanıcı nasıl fark eder → sadece log, admin panel UI kapsam dışı
   (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Başarı ölçütü → mock'lu unit testler, deterministik mantık (Sonnet 5
   alt-ajanı tarafından yanıtlandı)
7. Kapsam dışı → panel UI, günlük/haftalık limit, model sırası, formül
   düzeltmesi, throttle (Sonnet 5 alt-ajanı ve kullanıcı mesajından)
8. Bağımlılıklar → text_gen_parser.py, veri_cekici_ayristirici.py,
   junk-filtre'ye yakın nokta (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Performans → bellek-içi sayaç, dosya sadece restart'ta okunur (Sonnet
   5 alt-ajanı tarafından yanıtlandı)
10. Rollback → git revert yeterli (Sonnet 5 alt-ajanı tarafından
    yanıtlandı)
11. Kabul kriteri → kullanıcı + otomatik test (Sonnet 5 alt-ajanı
    tarafından yanıtlandı)
12. Test stratejisi → 85/15/0 (Sonnet 5 alt-ajanı tarafından yanıtlandı)
13. Riskler/Assumptions → DeepSeek+Groq toplamı varsayımı, restart sonrası
    sayaç kurtarma riski, thread-safety riski (Sonnet 5 alt-ajanı
    tarafından yanıtlandı)
14. "Throttle değil, güvenlik ağı" talebi → kullanıcı mesajından, tekrar
    sorulmadı
