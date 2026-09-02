---
task_slug: deepseek-cost-fix
jira_id: null
saga_task_id: null
priority: critical
coverage_target: 85
performance_target: "provider seçim mantığı <5ms overhead, mesaj başına gecikme artışı gözle görülür olmamalı"
memory_target: null
test_strategy:
  unit: 70
  integration: 20
  e2e: 10
affected_modules:
  - text_gen_parser.py (models_to_try sıralaması, Groq client, retry/fallback mantığı, _track_spend)
  - src/utils/api_key_manager.py veya eşdeğeri (Groq key rotasyonu — dosya adı doğrulanmalı)
  - src/parsers/veri_cekici_ayristirici.py (orchestrator, quality_gate sonucu üzerinden fallback tetikleme)
  - .env / config.py (yeni GROQ_API_KEY(S), model isimleri)
  - data/ai_spend_history.json (maliyet geçmişi — provider bazlı ayrım eklenecek)
---

# ATDD — deepseek-cost-fix

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev.

## Persona
Sistem sahibi/operatör (Yusuf) — haftalık sabit bir AI bütçesiyle (500 TL/hafta) günde ~5000 WhatsApp mesajını işleten kişi.

## Hedef (Neden)
**Düzeltilen ilk varsayım:** Bu görev başlangıçta bir fiyatlandırma HESAPLAMA hatası (Gemini/DeepSeek fiyat karışıklığı) olarak çerçevelenmişti. Kullanıcı bunu düzeltti: **asıl sorun hesaplama değil, gerçek DeepSeek bakiyesinin hedeflenen hacimde çok hızlı tükenmesi.** Araştırma (bkz. Riskler/Varsayımlar) DeepSeek V4 Flash'ın (~$0.22/$0.66 per 1M token, off-peak) günde 5000 mesaj × 2 aşama = 10.000 çağrı hacminde haftalık ~660 TL'ye denk geldiğini, üstelik DeepSeek'in "peak" fiyatlandırma saatlerinin (01:00-04:00 ve 06:00-10:00 UTC, hafta içi = TR saatiyle 04:00-07:00 ve 09:00-13:00) kullanıcının en yoğun çalışma saatleriyle (07:00-23:00) çakıştığını gösterdi — bu da 500 TL/hafta bütçenin neden hızla tükendiğini açıklıyor. Karşılaştırmalı fiyat araştırması, Groq'un Llama modellerinin (~$0.05/$0.08 per 1M token) DeepSeek'ten ~5-6 kat daha ucuz olduğunu ve kodda zaten bir Groq client altyapısının (`_get_async_client()`) bulunduğunu ortaya çıkardı. Hedef: **Groq'u birincil (yüksek hacimli, düşük maliyetli) model yapmak, DeepSeek'i sadece Groq'un başarısız olduğu veya geçerli sonuç üretemediği (karmaşık) mesajlar için yedek olarak kullanmak** — böylece toplam maliyet 500 TL/hafta bütçenin rahatça altında kalır.

## User Story
As a sistem operatörü
I want günlük ~5000 mesajlık hacmi haftalık 500 TL bütçe içinde işleyebilen bir AI ayrıştırma zinciri
So that DeepSeek bakiyesi beklenmedik şekilde tükenmesin ve sistem kesintisiz çalışsın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given bir WhatsApp mesajı ayrıştırılmak üzere geldi, When Stage 1 (konum çıkarma) ve Stage 2 (tam ayrıştırma) çalıştırılır, Then her iki aşama da **önce Groq (Llama modeli) ile denenir** — DeepSeek ilk deneme olarak KULLANILMAZ.
2. [Critical] Given Groq denemesi bir API hatasıyla (4xx/5xx, timeout, rate limit) başarısız oldu, When retry mantığı devreye girer, Then sistem aynı mesaj için **DeepSeek'e otomatik olarak düşer (fallback)** ve bu geçiş loglanır (`[FALLBACK] Groq başarısız, DeepSeek deneniyor: <sebep>`).
3. [Critical] Given Groq API çağrısı BAŞARILI döndü ama üretilen sonuç `quality_gate` tarafından geçersiz/boş sayıldı (0 geçerli sevkiyat, "karmaşık mesaj" belirtisi), When bu durum tespit edilir, Then sistem aynı mesajı **DeepSeek ile tekrar dener** (bu da bir fallback sayılır, sadece HTTP hatası değil, kalite hatası da tetikleyici).
4. [High] Given hem Groq hem DeepSeek denemesi başarısız oldu, When tüm modeller tükendi, Then mevcut davranış korunur — `PARSE FAILED: All models exhausted` loglanır, mesaj işlenemedi olarak işaretlenir (mevcut sistemle aynı, değişmiyor).
5. [High] Given Groq'un ücretsiz/ücretli kota limiti (RPM/RPD) aşıldı, When 429 hatası alınır, Then mevcut key-rotasyon mantığı (`key_manager.switch_to_next_async(key_type='groq', ...)`) önce başka bir Groq anahtarına geçmeyi dener, TÜM Groq anahtarları tükendiyse DeepSeek'e düşer.
6. [Medium] Given bir mesaj Groq ile başarıyla işlendi, When `_track_spend()` çağrılır, Then maliyet kaydı hangi provider'ın (Groq/DeepSeek) kullanıldığını AYIRT EDECEK şekilde tutulur (mevcut `ai_spend_history.json` şemasına `provider` alanı eklenir) — böylece haftalık Groq/DeepSeek harcama oranı panelde/loglarda görülebilir.
7. [Medium] Given sistem 1 hafta gerçek trafikte çalıştı, When toplam harcama hesaplanır, Then toplam maliyet **500 TL/hafta bütçesinin altında** kalır (izleme kriteri, otomatik test değil — kullanıcı 1 hafta sonra doğrular).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: Groq ilk denemede başarılı | Parse sonucu (shipments listesi) | `ai_spend_history.json`'a `provider: "groq"` ile 1 kayıt | Mesaj normal hızda işlenir, maliyet düşük | AC-1, AC-6 |
| 2 | Groq API hatası (4xx/5xx/timeout) | İç retry sonrası DeepSeek'e geçiş | `[FALLBACK]` log satırı, DeepSeek çağrısı yapılır | Küçük ek gecikme (birkaç saniye), sonuç yine üretilir | AC-2 |
| 3 | Groq başarılı ama sonuç geçersiz (karmaşık mesaj) | Quality gate reddi → DeepSeek ile yeniden deneme | `[FALLBACK]` log (sebep: "kalite yetersiz"), 2. bir API çağrısı (maliyet artışı, ama nadiren) | Mesaj yine de doğru işlenir, sadece Groq yerine DeepSeek maliyeti oluşur | AC-3 |
| 4 | Hem Groq hem DeepSeek başarısız | `[]` (boş liste), `PARSE FAILED` logu | Mesaj `onaylanmamis`a işaretlenmez, tekrar denenebilir kalır | Panelde mesaj görünmez/işlenmemiş kalır | AC-4 |
| 5 | Groq kota/rate-limit (429) | Key rotasyonu, sonra DeepSeek fallback | Key rotasyon logu + gerekirse fallback logu | Görünür bir etki yok (sistem içi geçiş) | AC-5 |
| 6 | Kaynak yok / `ai_spend_history.json` bozuk | Mevcut `load_json_safe` davranışı korunur | Kayıt kaybı riski loglanır, sistem çökmez | Panelde geçmiş veri eksik görünebilir | *(bu görevde davranış değişmiyor)* |
| 7 | **Kısmi başarı**: Stage 1 Groq ile başarılı, Stage 2 hem Groq hem DeepSeek'te başarısız | Stage 1 sonucu var, Stage 2 `[]` | Stage 1 maliyeti kaydedilir, Stage 2 için `PARSE FAILED` | Mesaj eksik/işlenmemiş sayılır (mevcut sistemle aynı) | AC-4 |
| 8 | **Hiçbir şey yapılamadı ama hata yok**: Groq API key hiç tanımlı değil (yanlış deploy) | Sistem başlangıçta bunu tespit edip DeepSeek'i doğrudan birincil yapmalı mı, yoksa hata mı vermeli? | *(silindi — bu satır Unknown'a taşındı, karar netleşmeden AC yazılamaz)* | | |

Kısmi başarı: Stage 1 ve Stage 2 birbirinden bağımsız fallback zincirine sahiptir — biri Groq'ta başarılı, diğeri DeepSeek'e düşebilir; ikisi ayrı ayrı `ai_spend_history.json`'a yazılır, provider alanı farklı olabilir.
Hiçbir şey yapılamadı ama hata yok: Groq key tanımsız/geçersizse sistemin ne yapacağı netleşmedi (bkz. Unknowns) — plan adımında karar verilmeli: (a) DeepSeek'e doğrudan düş ve uyarı logla, (b) sistemi başlatma ve hata ver. Öneri (a), çünkü sistemin tamamen durması mesaj kaybına yol açar; ama bu bir varsayım, kullanıcı onayı gerekir.
Boş sonuç ↔ hata ayrımı: Bir mesaj için `ai_spend_history.json`'da hiç kayıt yoksa bu ya mesaj hiç işlenmedi (filtrelendi/mükerrer) ya da hem Groq hem DeepSeek başarısız oldu (AC-4) demektir; ayrım orchestrator loglarındaki `[SKIP]`/`PARSE FAILED` etiketleriyle yapılır, bu görev yeni bir ayrım mekanizması eklemiyor.

## Test Strategy
Unit: 70% — model seçim/fallback mantığı (Groq→DeepSeek geçiş koşulları: HTTP hata, quality-gate reddi, key tükenmesi), `_track_spend()`'in provider alanını doğru yazması. DeepSeek/Groq API'leri mock'lanır.
Integration: 20% — `parse_async()` uçtan uca akışı: Groq mock'ı başarısız dönünce gerçekten DeepSeek'in çağrılıp çağrılmadığı, quality-gate reddi senaryosunda ikinci denemenin tetiklenmesi.
E2E: 10% — VPS'te gerçek Groq + gerçek DeepSeek ile birkaç canlı mesaj (gerçek para/kota harcayacağı için minimal), ardından `ai_spend_history.json`'da provider dağılımının doğru göründüğünün doğrulanması.

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: Provider seçim/fallback mantığının kendisi <5ms ek yük getirmeli; happy-path (Groq başarılı) mesaj işleme süresi mevcut sistemden YAVAŞ olmamalı.
Diğer ölçülebilir kriterler:
- **1 haftalık gerçek kullanım sonunda toplam AI maliyeti 500 TL'nin altında kalmalı** (birincil başarı kriteri, kullanıcı doğrular).
- Mesajların **çoğunluğu** (kesin yüzde belirlenmedi — bkz. Unknowns) Groq ile ilk denemede başarıyla işlenmeli; DeepSeek fallback oranı görece düşük (azınlık) olmalı.
- `ai_spend_history.json`'daki provider dağılımı (Groq vs DeepSeek çağrı/maliyet oranı) panelde/loglarda izlenebilir olmalı.

## Kapsam Dışı
- Stage 1 + Stage 2 mimarisinin birleştirilmesi/kaldırılması.
- Gemini'ye geçiş (araştırma sonucu mevcut hacimde DeepSeek'ten daha pahalı çıktı — Gemini 3.5 Flash $1.50/$9.00 per 1M, uygun değil).
- DeepSeek veya Groq hesap bakiyesinin otomatik doldurulması/ödeme entegrasyonu.
- Yerel/self-hosted model (Ollama vb.) — mevcut VPS (1.9GB RAM, 1 vCPU) kapasite olarak yetersiz, bu görevde değerlendirilmiyor.
- Groq'un Llama modelinin Türkçe lojistik metin ayrıştırma DOĞRULUĞUNUN DeepSeek ile birebir aynı olduğunun garanti edilmesi — bu görev maliyeti düşürmeyi hedefliyor, doğruluk karşılaştırması ayrı bir değerlendirme konusu (bkz. Riskler).

## Etkilenen Dosyalar/Modüller (bilinen)
- `text_gen_parser.py` — `models_to_try` sıralaması (Groq önce, DeepSeek sonra), Groq client zaten var (`_get_async_client`), quality-gate reddi üzerine fallback tetikleme mantığı YENİ eklenecek
- Groq API key yönetimi — `key_manager` (dosya konumu doğrulanmalı, muhtemelen `src/utils/` altında)
- `src/parsers/veri_cekici_ayristirici.py` — `quality_gate.evaluate()` sonucunu ikinci bir Groq/DeepSeek denemesi tetiklemek için kullanan orchestrator akışı
- `.env` — yeni geçerli `GROQ_API_KEY`/`GROQ_API_KEYS` (mevcut anahtar geçersizdi, bu görev başlamadan önce YENİ ve GEÇERLİ bir anahtar temin edilmeli)
- `data/ai_spend_history.json` — şemaya `provider` alanı eklenmesi (geriye dönük uyumluluk: eski kayıtlarda bu alan yok, okuma tarafı `None`/`"deepseek"` varsayımıyla çalışmalı)

## Rollback Beklentisi
Groq'un doğruluğu/kalitesi kabul edilemez çıkarsa (örn. Türkçe lojistik metinlerde DeepSeek'ten belirgin şekilde kötü sonuç üretirse), `models_to_try` sıralaması tek satırlık bir değişiklikle eski haline (DeepSeek önce) döndürülebilir olmalı — bu geri dönüş bir config/sabit değişikliği olmalı, kod mantığının yeniden yazılmasını gerektirmemeli.

## Risks
- **DeepSeek gerçek fiyatlandırması** (araştırmayla doğrulandı, 2026-08-24/25 itibariyle): V4 Flash off-peak $0.22(cache-miss)/$0.66 input/output per 1M, peak saatlerde 2x. Peak saatler (01:00-04:00, 06:00-10:00 UTC hafta içi) TR saatiyle 04:00-07:00 ve 09:00-13:00'e denk geliyor — sistemin aktif çalışma saatleriyle (07:00-23:00) kısmen çakışıyor. [Kaynak: DeepSeek resmi fiyatlandırma sayfaları, WebSearch ile doğrulandı]
- **Groq fiyatlandırması** (Llama 3.1 8B Instant): $0.05 input / $0.08 output per 1M token — DeepSeek'ten ~5-6 kat ucuz. Groq'un ücretsiz kota limitleri (RPM/RPD) 10.000 çağrı/gün hacminde muhtemelen yetersiz kalacak, ÜCRETLİ Groq kullanımı gerekecek (yine de çok ucuz).
- **Groq doğruluk riski**: Llama 3.1 8B küçük bir model — Türkçe lojistik metinlerdeki karmaşık/çok satırlı ilanlarda DeepSeek kadar doğru ayrıştırma yapamayabilir. Bu, AC-3'teki "kalite yetersizse DeepSeek'e düş" mekanizmasıyla kısmen telafi ediliyor ama gerçek kullanımda test edilmeli.
- **Önceki oturumda Groq key'i geçersizdi** (401 Invalid API Key) ve bu yüzden tamamen kaldırılmıştı — bu görev başlamadan önce **YENİ VE GEÇERLİ bir Groq API key** (console.groq.com üzerinden) temin edilmesi ön koşuldur, yoksa fallback zinciri baştan çalışmaz.

## Assumptions
- Kullanıcının belirttiği "günlük 5000 mesaj" rakamı, Stage 1 + Stage 2 ile birlikte günde ~10.000 API çağrısına denk geliyor (2 aşama × 5000 mesaj) — bu görevde bu varsayımla ilerleniyor, gerçek rakam farklıysa maliyet hesapları yeniden yapılmalı.
- "Karmaşık mesaj" tanımı, bu ATDD'de "Groq'un ürettiği sonucun `quality_gate` tarafından geçersiz/boş sayılması" olarak yorumlandı (ayrı bir "karmaşıklık skoru" hesaplayan yeni bir sınıflandırıcı YAZILMIYOR) — kullanıcı bunun yerine mesaj uzunluğu/yapısına göre PROAKTİF bir yönlendirme (Groq'a hiç denemeden DeepSeek'e gitme) istiyorsa bu görev kapsamı genişler, plan adımında teyit edilmeli.
- Groq API key'inin bu görev başlamadan önce (plan/code-copilot adımına geçmeden önce) kullanıcı tarafından temin edileceği varsayılıyor.

## Unknowns
- Groq key'i henüz temin edilmedi — hangi Groq modelinin (llama-3.1-8b-instant / llama-3.3-70b-versatile / başka) kullanılacağı, doğruluk/maliyet dengesine göre plan adımında test edilerek netleştirilmeli.
- Groq API key'i tanımsız/geçersiz olduğunda sistemin davranışı (doğrudan DeepSeek'e düş mü, hata mı versin) netleşmedi — bkz. Davranış Sözleşmesi tablosundaki 8. satır.
- "Mesajların çoğunluğu Groq'ta başarılı olmalı" hedefi için kesin bir yüzde eşiği belirlenmedi (örn. %80, %90) — 1 haftalık gerçek kullanım verisiyle plan adımında somutlaştırılabilir.
- Groq'un ücretsiz/ücretli kota limitlerinin (RPM/RPD) tam değerleri bu görevde teyit edilmedi — code-copilot adımında console.groq.com üzerinden kontrol edilmeli.

## Sorular ve Cevaplar (ham kayıt)
1. İlk taslakta "sorun hesaplama hatası" varsayıldı → Kullanıcı düzeltti: "sorun ordaki hesaplama değil sorun gerçeketen hızlı bir şekilde bitmesi alternatif model yada abonelik ihtiyacımız var" (kullanıcı mesajından).
2. Bütçe/hacim → "haftalık 500 tl ye göre planla günlük 5000 mesaj" (kullanıcı mesajından).
3. Hangi yön (Gemini/DeepSeek abonelik/başka sağlayıcı/hibrit) → "Groq + DeepSeek hibrit, başka bir dağılım öneriyorum" (kullanıcı mesajından) — Claude'un araştırmasına (Groq'un en ucuz seçenek olduğu) dayanarak Groq'u birincil öneren seçenek kullanıcı tarafından üstü kapalı onaylandı, tam dağılım kullanıcıdan istendi.
4. Dağılım detayı → "önce Groq, başarısız/karmaşık mesajlarda DeepSeek'e düş" (kullanıcı mesajından) — "karmaşık" ifadesi bu ATDD'de quality-gate reddi olarak yorumlandı, Unknowns'a not düşüldü.
5. Fiyat araştırması (DeepSeek, Gemini 3.5 Flash, Gemini 2.5 Flash-Lite, Groq Llama 3.1 8B) → WebSearch ile 2026-08-24/25 itibariyle doğrulandı (Claude tarafından araştırıldı, kullanıcıya soru olarak sorulmadı — doğrudan teknik araştırma).
