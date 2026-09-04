---
task_slug: deepseek-maliyet-dusurme-stage-birlestir-junk-filtre
jira_id: null
saga_task_id: null
priority: high
coverage_target: 80
performance_target: null
memory_target: null
test_strategy:
  unit: 75
  integration: 20
  e2e: 5
affected_modules:
  - text_gen_parser.py
  - src/parsers/veri_cekici_ayristirici.py
---

# ATDD — deepseek-maliyet-dusurme-stage-birlestir-junk-filtre

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga bağlantısı bu oturumda kurulamadı
(önceki görevlerle aynı MCP timeout sorunu) — `saga_task_id: null`.

## Persona
Sistem operatörü (kullanıcı) — günlük 80 TL DeepSeek bütçesiyle günün
tamamını (09:00-23:00, ~14 saat) kapsamak istiyor, şu anki mimariyle bu
bütçe sadece ~4 saat sürüyor.

## Hedef (Neden)
`deepseek-saatlik-sabit-maliyet-kaynagi` görevinde (bu oturumun önceki
adımı) bulunan gerçek kök neden: her mesaj **iki ayrı DeepSeek çağrısı**
üretiyor (Stage 1: rota çıkarımı, Stage 2: tam JSON ayrıştırma). Kullanıcı
önce throttle/rate-limit (bütçeyi saatlere bölmek) önerisini AÇIKÇA
REDDETTİ — "ikiside yetersiz 5 tl ile saat başı adam akıllı iş yapamayız"
— gerçek talep işi YAVAŞLATMAK değil, **maliyetin kendisini düşürmek** ki
aynı bütçe daha fazla saat/mesaj kapsasın. Bu görev iki değişikliği
kapsıyor:
1. Stage 1 + Stage 2'yi TEK bir DeepSeek çağrısında birleştirmek (mesaj
   başına ~2 çağrıyı ~1'e indirir, baseline maliyeti ~%50 azaltır).
2. Kuyruğa girmeden önce ucuz/yerel (LLM'siz) bir "junk filtresi" ile
   bariz alakasız mesajları hiç API'ye göndermeden elemek.

DeepSeek hesabında şu an bakiye YOK (402 Insufficient Balance,
[önceki bulgu](../deepseek-saatlik-sabit-maliyet-kaynagi/plan.md)) — bu
görevin testleri MOCK'LANACAK, gerçek maliyet düşüşü bakiye yüklenince
kullanıcı tarafından prod'da (VPS: 161.35.126.250) doğrulanacak. Bu,
görevin "tamamlandı" sayılması için ŞART DEĞİL (kod/mock-test kanıtı
yeterli), ama nihai kanıt bu olacak.

## User Story
As a sistem operatörü
I want mesaj başına DeepSeek çağrı sayısını 2'den 1'e indiren bir
birleştirme VE bariz junk mesajları LLM'e hiç göndermeyen bir yerel filtre
So that aynı 80 TL/gün bütçesiyle günün tamamını (14 saat) kapsayabileyim,
throttle'a (mesaj atlamaya) gerek kalmadan

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `text_gen_parser.py`'nin `parse_async()` fonksiyonu,
   When bir mesaj işlenir, Then Stage 1 (`_extract_locations_stage1_async`)
   AYRI bir API çağrısı olarak ÇAĞRILMAMALI — tagged-cities hint doğrudan
   Stage 2'nin (mevcut ana JSON ayrıştırma) promptuna gömülmeli, mesaj
   başına DeepSeek+Groq baseline çağrı sayısı ~2'den ~1'e düşmeli (retry
   hariç).
2. [Critical] Given birleştirilmiş tek çağrı, When mevcut retry+model-
   fallback zinciri (DeepSeek→Groq, 3 deneme) çalışır, Then bu zincir
   AYNEN korunmalı — sadece "2 aşama x kendi zincir" yerine "1 aşama x
   aynı zincir" olmalı, davranış sözleşmesi değişmemeli (regresyon testi).
3. [Critical] Given `add_to_processing_queue()`'ya gelen bir mesaj VE
   içinde hiçbir Türkiye şehir adı, hiçbir lojistik anahtar kelimesi
   (TIR, boş araç, nakliye, yük vb.) ve hiçbir telefon numarası formatı
   YOK, When yeni `_is_junk_message()` heuristic'i çalışır, Then bu mesaj
   DeepSeek'e hiç gönderilmeden elenmeli VE loglanmalı/ayrı bir
   "filtered" listesine düşmeli (sessizce kaybolmamalı).
4. [High] Given bir mesajda şehir adı YOK ama lojistik anahtar kelimesi
   VEYA telefon numarası formatı VAR, When junk filtresi çalışır, Then
   filtre PAS GEÇMELİ — mesaj LLM'e gönderilmeye devam etmeli (muhafazakar
   eşik, false-positive riski öncelikli).
5. [High] Given `data/onaylanmamis_ayristirilmis_log.json`'daki gerçek
   geçmiş mesaj örnekleri (en az 20-30 tanesi test setine alınacak), When
   junk filtresi bu örnekler üzerinde test edilir, Then GERÇEK bir ilan
   YANLIŞLIKLA elenmemeli (false-positive oranı %0 olmalı).
6. [Medium] Given birleştirilmiş çağrı boş/geçersiz JSON (`routes: []`)
   döner, When bu son model değilse, Then mevcut davranış (satır 548-551:
   break edip sıradaki modele geç) DEĞİŞMEMELİ (regresyon testi).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: birleştirilmiş tek çağrı | Normal parse sonucu (routes listesi) | Mesaj başına ~1 DeepSeek+Groq baseline çağrısı (2 değil) | Panelde değişiklik yok (şeffaf) | AC-1,2 |
| 2 | Girdi geçersiz/eksik: mesaj bariz junk (şehir/anahtar kelime/telefon YOK) | `_is_junk_message()` True döner, queue'ya girmeden elenir | Loglanır + "filtered" listesine düşer | Panelde hiç görünmez ama loglarda iz bırakır | AC-3 |
| 3 | Kaynak yok/şüpheli: şehir yok ama anahtar kelime/telefon VAR | Filtre False döner (junk değil) | LLM'e gönderilmeye devam eder | Normal işlenir | AC-4 |
| 4 | Dış bağımlılık hatası (429/402/timeout) | Mevcut retry (3 deneme) + model-fallback (DeepSeek→Groq) zinciri aynen çalışır | Değişmez | Değişmez | AC-2 |
| 5 | **Kısmi başarı**: belirsiz junk sinyali (bazı işaretler var bazı yok) | Muhafazakar kural: TEK bir olumlu sinyal (şehir/anahtar kelime/telefon) bile varsa LLM'e gönder | Değişmez | Normal işlenir | AC-4 |
| 6 | **Hiçbir şey yapılamadı ama hata yok**: birleştirilmiş çağrı `routes: []` döner | Mevcut davranış korunur — son model değilse sıradaki modele geç, son modelse `_process_raw_json_async`'e düşer | Değişmez | Değişmez | AC-6 |

Boş sonuç ↔ hata ayrımı: Junk filtresinin elediği mesaj ("bu bir ilan
değil") ile LLM'in boş routes döndürdüğü mesaj ("ilan gibi ama parse
edilemedi") AYRI loglanmalı — ikisi karıştırılmamalı, biri filtre
aşamasında biri LLM aşamasında düşüyor.

Yetkisiz erişim / Zaman aşımı (ayrı satır olarak): Zaman aşımı zaten
Satır 4'teki "dış bağımlılık hatası" kapsamında ele alınıyor, ayrı satır
gereksiz — silindi. Yetkisiz erişim bu görevde N/A (kimlik doğrulama
katmanı yok) — silindi.

## Test Strategy
Unit: 75% — `_is_junk_message()` heuristic'inin karar mantığı (şehir/
anahtar kelime/telefon kombinasyonları), birleştirilmiş promptun doğru
oluşturulduğu (Stage 1'in hint mantığının Stage 2 promptuna doğru
gömüldüğü), retry/fallback zincirinin değişmediği (mock'lu)
Integration: 20% — `add_to_processing_queue()`'nun junk filtresini
gerçekten çağırdığı ve filtrelenen/filtrelenmeyen mesajların doğru
yollara gittiği uçtan uca (mock API)
E2E: 5% — gerçek DeepSeek bakiyesi yok, bu oran şu an çalıştırılamıyor;
kullanıcı bakiye yüklenince prod'da manuel doğrulayacak

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: yok
Memory: yok
Diğer ölçülebilir kriterler:
- Mock testlerle mesaj başına DeepSeek+Groq çağrı sayısı ortalamasının
  ~2'den ~1'e düştüğü (retry hariç baseline) ÖLÇÜLEBİLİR şekilde
  doğrulanmalı.
- `data/onaylanmamis_ayristirilmis_log.json`'dan alınan en az 20-30 GERÇEK
  mesaj örneği üzerinde junk filtresinin false-positive oranı **%0**
  olmalı.
- Gerçek maliyet düşüşü: kullanıcı DeepSeek bakiyesini yükleyince prod'da
  (VPS) saatlik $ harcamasının gözlemlenmesiyle NİHAİ olarak doğrulanacak
  (kod dışı, bu görevin tamamlanma şartı değil ama hedeflenen sonuç).

## Kapsam Dışı
- Model seçimi/sırası (DeepSeek primary, Groq fallback) — DEĞİŞMİYOR, bu
  ayrı bir tartışmaydı (Groq'u primary yapmak öneri olarak konuşuldu ama
  kullanıcı bu görevde onu istemedi).
- Retry sayısı (3), `max_tokens`, JSON şema — değişmiyor.
- Throttle/rate-limit/bütçe-tavanı mekanizması — kullanıcı bunu AÇIKÇA
  reddetti, bu görevin kapsamında DEĞİL.
- `_track_spend()`'in maliyet formülü (cache-hit/miss fiyat ayrımı,
  önceki oturumda tartışıldı) — AYRI bir konu, bu görev sadece çağrı
  SAYISINI azaltıyor, formülü düzeltmiyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `text_gen_parser.py` (`_extract_locations_stage1_async` kaldırılacak/
  birleştirilecek, `parse_async`'in promptu genişleyecek)
- `src/parsers/veri_cekici_ayristirici.py` (`add_to_processing_queue()`'ya
  yeni `_is_junk_message()` helper eklenecek)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımından önce `git rev-parse --show-toplevel` ile
kontrol edilecek. Bu oturumdaki aramalar worktree kökünde kaldı.

## Rollback Beklentisi
Düz kod değişikliği, migrasyon yok. Sorun çıkarsa `git revert` yeterli.

## Risks
- Stage 1'in kaldırılmasının parse doğruluğunu (özellikle çok-bölümlü/
  karmaşık mesajlarda rota tespitini) düşürüp düşürmeyeceği kod incelemesi
  olmadan KESİN bilinmiyor — `plan` adımında Stage 1'in çıktısının Stage
  2'ye GERÇEKTEN aktarılıp aktarılmadığı (yoksa sadece paylaşılan bir
  regex "hint" mi) kod okunarak netleştirilmeli. Eğer Stage 1'in kendi
  çıktısı (temiz "ORIGIN -> DESTINATION" satırları) Stage 2'ye ayrıca
  besleniyorsa, bu görev daha karmaşık hale gelir (basit silme yetmez).
- Junk filtresinin gerçek üretim çeşitliliğini (emoji-ağırlıklı, kısaltma
  bolluğu, yabancı dil karışık mesajlar) yeterince kapsamaması riski —
  bu yüzden AC-5'te gerçek geçmiş veri üzerinde test şart koşuldu.

## Assumptions
- Stage 1'in çıktısının Stage 2'ye AYRICA beslenmediği, sadece paylaşılan
  bir `_tag_cities`/`_clean_message` regex hint'inin kullanıldığı
  VARSAYILIYOR — bu VARSAYIM, `plan` adımında kod okunarak KESİNLEŞTİRİLMELİ
  (Unknown, aşağıda tekrar).

## Unknowns
- Stage 1'in çıktısı (`_extract_locations_stage1_async`'in döndürdüğü
  temiz rota satırları) `parse_async` içinde GERÇEKTEN kullanılıyor mu,
  yoksa sadece regex tag hint'i mi paylaşılıyor? `plan` adımında
  [text_gen_parser.py:330-460](text_gen_parser.py:330) okunarak
  kesinleştirilecek.
- `_tag_cities()`'in kullandığı şehir/hub/alias listesinin (satır 175-179)
  junk filtresi için YETERLİ kapsamda olup olmadığı (bazı küçük ilçeler
  eksik olabilir) — `plan` adımında değerlendirilecek.

## Sorular ve Cevaplar (ham kayıt)
1. Happy path/birleştirme yaklaşımı → Stage 1'i tamamen kaldır, hint'i
   Stage 2 promptuna göm (Sonnet 5 alt-ajanı tarafından yanıtlandı)
2. Edge case'ler → Stage 1 çıktısı muhtemelen bağımsız kullanılmıyordu
   (plan'da kesinleşecek), false-positive junk loglanmalı, filtre eşiği
   muhafazakar (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Davranış sözleşmesi → mevcut retry/fallback zinciri aynen korunur,
   sadece aşama sayısı azalır (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. Kısmi başarı → anahtar kelime/telefon varsa LLM'e gönder, hiçbir sinyal
   yoksa ele (Sonnet 5 alt-ajanı tarafından yanıtlandı)
5. Hiçbir şey yapılamadı ama hata yok → mevcut boş-routes/fallback mantığı
   değişmez (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Başarı ölçütü → çağrı sayısı ~2'den ~1'e (mock), junk filtre %0 false-
   positive (gerçek veri üzerinde), gerçek maliyet düşüşü prod'da nihai
   doğrulama (Sonnet 5 alt-ajanı tarafından yanıtlandı)
7. Kapsam dışı → model sırası, retry sayısı, max_tokens, JSON şema, throttle
   (kullanıcı reddetti), _track_spend formülü (Sonnet 5 alt-ajanı ve
   kullanıcı mesajından)
8. Bağımlılıklar → text_gen_parser.py, veri_cekici_ayristirici.py (Sonnet
   5 alt-ajanı tarafından yanıtlandı)
9. Performans/güvenlik kısıtı → yok (Sonnet 5 alt-ajanı tarafından
   yanıtlandı)
10. Rollback → git revert yeterli (Sonnet 5 alt-ajanı tarafından
    yanıtlandı)
11. Kabul kriteri → kod/mock-test kanıtı yeterli, gerçek maliyet düşüşü
    prod'da ayrıca doğrulanacak ama şart değil (Sonnet 5 alt-ajanı
    tarafından yanıtlandı)
12. Test stratejisi → 75/20/5, bakiye olmadığı için e2e minimum (Sonnet 5
    alt-ajanı tarafından yanıtlandı)
13. Riskler/Unknown'lar → Stage 1 çıktısının Stage 2'ye aktarılıp
    aktarılmadığı netleşmemiş, plan'da kod okunarak kesinleşecek (Sonnet
    5 alt-ajanı tarafından yanıtlandı)
14. Throttle reddi/gerçek maliyet talebi → kullanıcı mesajından, tekrar
    sorulmadı ("ikiside yetersiz 5 tl ile saat başı adam akıllı iş
    yapamayız")
