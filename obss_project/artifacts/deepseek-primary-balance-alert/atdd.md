---
task_slug: deepseek-primary-balance-alert
jira_id: null
saga_task_id: null
priority: critical
coverage_target: 80
performance_target: "bakiye kontrolü mesaj işleme akışını yavaşlatmaz (arka planda, periyodik)"
memory_target: null
test_strategy:
  unit: 75
  integration: 25
  e2e: 0
affected_modules:
  - text_gen_parser.py
  - src/api/admin_panel.py
---

# ATDD — deepseek-primary-balance-alert

## OLAY ÖZETİ VE KARAR GEÇMİŞİ (bu oturumda)
2026-08-30, ~21:49: Groq'un 5 API anahtarının hepsi günlük token
limitine (TPD) ulaştı VE DeepSeek'in bakiyesi aynı anda bitti — sistem
"PARSE FAILED: All models exhausted" durumuna düştü, hiçbir mesaj
işlenemedi. Bu, müşterinin "kasa tipi yansımıyor" ve "10-11 arası işlem
yapılmadı" şikayetlerinin doğrudan nedeniydi.

İlk çözüm önerisi olarak self-hosted GPU (RunPod Serverless) araştırıldı
(bkz. `obss_project/artifacts/serverless-gpu-parser/` — bu görev TERK
EDİLDİ). Araştırma sonucu: bu ölçekte (günde 5000 mesaj, düzensiz/seyrek
gelen kısa mesajlar) kendi GPU kiralamanın maliyeti (~$30-60/ay, model
boyutundan bağımsız olarak cold-start ek yükü baskın olduğu için küçük
model de dramatik ucuzlatmıyor) paylaşımlı bir API'den (DeepSeek) daha
PAHALI çıkıyor — kendi GPU'nun ölçek avantajı yok. Kullanıcı bu analizden
sonra self-host fikrini bıraktı.

**Gerçek kök neden mimari değil, operasyoneldi**: DeepSeek'in kendisi
zaten bu iş için yeterince ucuz ve GÜNLÜK LİMİTİ YOK (Groq'un aksine) —
sadece prepaid bakiyesi kimse fark etmeden bitti. Çözüm: DeepSeek'i
birincil model yap (Groq'un günlük-limit riskine bağımlılığı azalt) ve
bakiye belirli bir eşiğin altına düştüğünde PROAKTİF bir uyarı üret —
böylece bakiye sıfıra inmeden biri fark edip doldurabilir.

## Persona
Sistem kendisi (arka plan parse pipeline'ı) + admin panel'i düzenli
kontrol eden operasyon ekibi/kullanıcı (bakiye uyarısını görecek olan).

## Hedef (Neden)
Groq'un günlük token limitine (TPD) bağımlılığı azaltmak (DeepSeek'i
öncelikli model yaparak) ve DeepSeek bakiyesinin sessizce sıfıra
inip TAM KESİNTİYE yol açmasını önlemek (proaktif bakiye uyarısıyla).

## User Story
As a operasyon ekibi
I want DeepSeek bakiyesi düşerken önceden haberdar olmak ve sistemin
Groq'un günlük limitine daha az bağımlı çalışmasını
So that geçen haftaki gibi TÜM modellerin aynı anda tükenip tam bir
kesintiye yol açtığı bir durumla bir daha karşılaşmayalım.

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `text_gen_parser.py`'nin model zinciri, When bir mesaj
   ayrıştırılır, Then `deepseek-v4-flash` (veya mevcut DeepSeek model adı)
   İLK denenen model olur — `openai/gpt-oss-20b` (Groq) SIRADAKİ fallback
   olarak kalır (kaldırılmıyor, sırası değişiyor).
2. [Critical] Given DeepSeek'in `/user/balance` API'si (`GET
   https://api.deepseek.com/user/balance`, `Authorization: Bearer <key>`),
   When sistem arka planda periyodik olarak (ör. her 15 dakikada bir) bu
   uç noktayı kontrol eder, Then dönen `is_available` alanı `false` İSE
   VEYA `total_balance` belirlenen bir eşiğin (ör. $5) altındaysa, bir
   uyarı durumu tetiklenir.
3. [High] Given bir bakiye uyarısı tetiklendi, When admin panel'in
   `/api/status` endpoint'i çağrılır, Then yanıt, mevcut `service`/`system`
   alanlarına ek olarak bir `deepseek_balance` alanı içerir (ör.
   `{"available": true/false, "balance_usd": 12.34, "low": true/false}`)
   — panel arayüzünde görsel olarak (ör. kırmızı rozet) gösterilebilir.
4. [High] Given DeepSeek API'sine bakiye kontrolü isteği ATILAMAZSA (ağ
   hatası, API kendisi geçici olarak erişilemez), When periyodik kontrol
   çalışırsa, Then bu bir "bilinmiyor" (`unknown`) durumu olarak
   işaretlenir — YANLIŞLIKLA "bakiye yeterli" (`available: true`) VEYA
   sistem çökmesi OLMAZ, sadece bir önceki bilinen durum korunur/loglanır.
5. [Medium] Given DeepSeek İLK model olarak deneniyor ama başarısız
   olursa (bakiye biterse, ağ hatası vb.), When mesaj işlenirken bu
   gerçekleşirse, Then mevcut "model başarısız, sıradakini dene" mantığı
   (zaten var, DEĞİŞTİRİLMİYOR) Groq'a (`openai/gpt-oss-20b`) geçer —
   sıra değişikliği bu fallback mekanizmasını BOZMAZ.
6. [Medium] Given periyodik bakiye kontrolü arka planda çalışıyor, When
   sistem başlangıçta (`RUNPOD...` değil, bu görevde `DEEPSEEK_API_KEY`)
   hiç tanımlı değilse, Then bakiye kontrolü hiç başlatılmaz, hata
   fırlatılmaz (mevcut `_refresh_status_cache`/`_start_bg_loader` deseniyle
   tutarlı bir "opsiyonel özellik, env yoksa sessizce atlanır" davranışı).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | AC |
|---|---|---|---|---|
| 1 | DeepSeek birincil, başarılı | Mevcut route JSON şeması | Mesaj işlenir | AC-1 |
| 2 | Bakiye düşük/tükenmiş | `/api/status`'ta `deepseek_balance.low: true` | Panelde görsel uyarı | AC-2, AC-3 |
| 3 | Bakiye API'sine erişilemiyor | `/api/status`'ta `deepseek_balance.available: "unknown"` | Önceki bilinen durum korunur, hata fırlatılmaz | AC-4 |
| 4 | DeepSeek başarısız, Groq'a geçiş | Mevcut fallback davranışı (DEĞİŞMEDİ) | Mesaj yine de işlenmeye çalışılır | AC-5 |
| 5 | `DEEPSEEK_API_KEY` tanımsız | Bakiye kontrolü hiç başlamaz, hata yok | Sistem mevcut haliyle çalışmaya devam eder | AC-6 |

Kısmi başarı: Bu görevde atomik bir "kısmi başarı" senaryosu yok (bakiye
kontrolü ya başarılı ya "unknown" döner, AC-4 bunu kapsıyor).
Hiçbir şey yapılamadı ama hata yok: AC-6'da ele alındı.
Boş sonuç ↔ hata ayrımı: `available: "unknown"` (API'ye ulaşılamadı) ile
`available: false` (API'ye ulaşıldı, bakiye gerçekten yetersiz) AÇIKÇA
ayrı durumlar (AC-4) — aynı değeri döndürmek YASAK, çünkü ilki "geçici
sorun" ikincisi "gerçek acil durum" anlamına geliyor.

## Test Strategy
Unit: 75% — model sırası değişikliğinin `models_to_try` listesinde doğru
yansıdığı, bakiye kontrol fonksiyonunun `is_available`/`total_balance`
alanlarını doğru yorumladığı, ağ hatası durumunda "unknown" döndüğü
(mock'lanmış HTTP yanıtlarıyla).
Integration: 25% — GERÇEK DeepSeek `/user/balance` endpoint'ine (mevcut
API key ile) bir istek atıp gerçek yanıt şemasının beklenenle uyumlu
olduğunun doğrulanması (bakiyeyi HARCAMAYAN, sadece OKUYAN bir GET
isteği — güvenli).
E2E: 0% — UI değişikliği minimal (mevcut panel'e bir alan ekleniyor),
ayrı bir e2e senaryosuna gerek yok.

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: Bakiye kontrolü arka planda, mesaj işleme akışını
BLOKLAMAZ (mevcut `_refresh_status_cache` deseniyle aynı — ayrı thread,
periyodik, sonucu cache'ler).
Diğer ölçülebilir kriterler: Bakiye $5'in altına düştüğünde `/api/status`
yanıtında `low: true` göründüğü canlı ortamda (gerçek API ile) doğrulanacak.

## Kapsam Dışı
- Otomatik bakiye doldurma (ödeme entegrasyonu) — bu, gerçek bir ödeme
  işlemi gerektirir, kullanıcı manuel yapmalı (sistem sadece UYARIR).
- Groq'un TAMAMEN kaldırılması — hâlâ fallback olarak kalıyor.
- SMS/e-posta/Telegram bildirimi — bu görevde sadece admin panel'in
  `/api/status`'una eklenen bir alan yeterli görülüyor; ayrı bir bildirim
  kanalı istenirse ayrı bir görev.
- `serverless-gpu-parser` görevinin devamı — o görev TERK EDİLDİ, bu
  görev onun yerine geçiyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `text_gen_parser.py` — `models_to_try` sırası (satır 271, 445 civarı).
- `src/api/admin_panel.py` — `_refresh_status_cache()`'e benzer bir arka
  plan bakiye-kontrol thread'i, `/api/status` yanıtına yeni alan.

## Rollback Beklentisi
Model sırası değişikliği geri alınabilir (basit liste sırası değişimi,
git revert ile). Bakiye kontrolü tamamen ek/opsiyonel bir özellik —
kaldırılması mevcut parse akışını etkilemez.

## Risks
- DeepSeek'i birincil yapmak, Groq'un (çoğunlukla ücretsiz) yerine
  DeepSeek'in (ücretli, token-bazlı) daha SIK kullanılmasına yol açar —
  bu, aylık maliyeti artırabilir (önceki oturumda Groq'un tam olarak BU
  YÜZDEN birincil yapıldığı unutulmamalı — bkz. `deepseek-cost-fix`
  görevi). Kullanıcı bu geri-dönüşü (Groq-öncelikli mimariden DeepSeek-öncelikliye)
  BİLEREK onayladı (maliyet/kesinti riski dengesini kesinti riskini
  azaltma yönünde tercih etti) — ama gerçek aylık maliyet etkisi
  izlenmeli.
- `/user/balance` API'sinin kendisi rate-limit'e takılabilir (15 dakikada
  bir kontrol, düşük sıklıkta — bu riski minimize ediyor).

## Assumptions
- DeepSeek API key'i (`DEEPSEEK_API_KEY`, `.env`'de zaten mevcut)
  `/user/balance` endpoint'ine erişim için yeterli (aynı key, ek bir
  yetkilendirme gerekmiyor — DeepSeek dokümantasyonuna göre).
- $5 eşiği (AC-2) makul bir varsayılan — kullanıcı onayı gerekiyor, plan
  aşamasında teyit edilecek.

## Unknowns
- Yok — araştırma ile netleşti.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı kararı: self-host GPU fikri bırakıldı → "DeepSeek'i birincil
   yap + bakiye uyarı sistemi" (kullanıcı mesajından, birebir).
2. DeepSeek `/user/balance` API'si var mı → Web araştırmasıyla
   doğrulandı: `GET https://api.deepseek.com/user/balance`, `is_available`
   + `balance_infos[].total_balance` döndürüyor.
3. Uyarı kanalı → Admin panel'in mevcut `/api/status` endpoint'ine
   eklendi (ben önerdim, mevcut deseni kullanıyor, ayrı bir bildirim
   kanalı istenmedi — plan onayında teyit edilecek).
4. Bakiye eşiği ($5) → Ben önerdim (makul bir varsayılan), kullanıcı
   onayı plan aşamasında.
