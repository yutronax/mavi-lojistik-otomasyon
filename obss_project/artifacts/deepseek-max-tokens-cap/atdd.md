---
task_slug: deepseek-max-tokens-cap
jira_id: null
saga_task_id: null
priority: high
coverage_target: 90
performance_target: null
memory_target: null
test_strategy:
  unit: 90
  integration: 10
  e2e: 0
affected_modules:
  - text_gen_parser.py
---

# ATDD — deepseek-max-tokens-cap

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev.

## OLAY ÖZETİ — Bu görev neden var
Kullanıcı: "DeepSeek maliyeti arttığında inanılmaz hızlı bitiyor, buna
çözüm bulmalıyız, aylık 2000 TL'ye mesajları işlemeliyiz."

**Kod incelemesiyle doğrulanan kesin bulgu:** `text_gen_parser.py`'de
DeepSeek/Groq'a route-extraction için yapılan 4 API çağrısında (Stage 1:
satır 279, 290; Stage 2: satır 465, 476) `max_tokens` parametresi HİÇ
ayarlanmamış — sadece alakasız küçük bir yardımcı çağrıda (satır 822)
`max_tokens=20` var.

**Production verisiyle doğrulanan etki** (`data/ai_spend_history.json`,
60.673 kayıt): Ağustos ayında DeepSeek çağrılarının **%79'u (8488/10761)
1000+ output token üretmiş**, medyan 2709 token (basit bir rota JSON'u
için normalde ~300-500 beklenirdi). En uç örnekler: TEK ÇAĞRIDA 42.787,
40.210, 36.749 token gibi devasa output'lar (normal bir çağrı ~500-750
token üretirken) — bu, modelin bir üretim döngüsüne girip durmadığının
(runaway generation) göstergesi.

**Simülasyon** (gerçek 4 aylık veriyle): `max_tokens=500` cap'i tüm
geçmişe uygulansaydı toplam maliyet **%16** azalırdı (2025 TRY → 1702
TRY). Gerçek aylık ortalama harcama (Temmuz ~1275 TL, Ağustos projeksiyon
~640 TL) zaten 2000 TL/ay hedefinin altında — asıl risk, nadir ama
devasa tekil çağrıların (30-40k token, tek başına ~0,34-0,43 TL) bakiyeyi
ANİDEN tüketmesi ve/veya küçük top-up miktarlarının normal kullanımla
bile hızlı tükenmesi.

**DeepSeek fiyatlandırması** (`text_gen_parser.py` satır 109): input
$0.27/1M token, output $1.10/1M token (output ~4x daha pahalı) —
runaway generation'ın maliyet etkisi bu yüzden orantısız büyük.

## Persona
Sistem kendisi (arka plan WhatsApp mesaj ayrıştırma pipeline'ı) — dolaylı
olarak sistemin operatörü (kullanıcı), aylık bütçe hedefine ulaşmak için.

## Hedef (Neden)
DeepSeek/Groq API çağrılarına bir üst token sınırı (`max_tokens`) koyarak,
nadir ama maliyeti orantısız yüksek "runaway generation" olaylarının
bakiyeyi aniden tüketmesini önlemek — aylık 2000 TL bütçe hedefine
ulaşmayı kolaylaştıran bir güvenlik ağı.

## User Story
As a sistem (mesaj ayrıştırma pipeline'ı)
I want her AI API çağrısına makul bir üst token sınırı koymak
So that nadir bir runaway generation olayı tek başına bakiyenin önemli
bir kısmını tüketmesin ve aylık maliyet öngörülebilir kalsın.

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given Stage 1'de bir DeepSeek veya Groq API çağrısı
   yapılıyor (satır ~279, ~290), When çağrı gönderiliyor, Then
   `max_tokens=1500` parametresi isteğe dahil edilir.
2. [Critical] Given Stage 2'de bir DeepSeek veya Groq API çağrısı
   yapılıyor (satır ~465, ~476), When çağrı gönderiliyor, Then
   `max_tokens=1500` parametresi isteğe dahil edilir.
3. [High] Given normal bir mesaj (1-3 rota) işleniyor, When AI yanıt
   üretiyor (~300-500 token), Then `max_tokens` cap'i hiç tetiklenmez,
   JSON eksiksiz döner, mevcut davranış DEĞİŞMEZ.
4. [High] Given AI yanıtı `max_tokens` sınırına takılıp kesiliyor
   (runaway VEYA gerçekten çok rotalı bir mesaj), When JSON parse
   edilmeye çalışılıyor, Then JSON parse hatası oluşur ve MEVCUT
   "sonraki modele/denemeye geç" fallback mantığı (DEĞİŞTİRİLMİYOR)
   devreye girer — ayrıca bu kesilme durumu ayrı bir log satırıyla
   (`truncated_at_max_tokens`) işaretlenir.
5. [Medium] Given `max_tokens` parametresi API tarafından reddedilir
   (geçersiz/desteklenmeyen — teorik, DeepSeek/Groq'un OpenAI-uyumlu
   API'leri bu parametreyi standart destekler), When istek başarısız
   olur, Then MEVCUT exception-yakalama ve fallback mantığı devreye
   girer (yeni bir hata sınıfı icat edilmiyor).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Normal mesaj (1-3 rota), cap'e takılmıyor | Eksiksiz JSON object (~300-500 token) | Yok — mevcut davranış | Sevkiyat(lar) normal şekilde işlenir | AC-3 |
| 2 | Çok rotalı mesaj (10+ rota), cap'e YAKLAŞIYOR ama takılmıyor | Eksiksiz JSON object (1200-1450 token) | Yok | Tüm rotalar işlenir | AC-3 |
| 3 | JSON `max_tokens`'a takılıp kesiliyor (runaway VEYA gerçekten çok-rotalı) | JSON parse hatası (eksik `}`/`]`) | MEVCUT fallback (sonraki model/deneme) tetiklenir + `truncated_at_max_tokens` logu | Mesaj bir sonraki model/denemeyle işlenmeye devam eder, kullanıcı fark etmez (mevcut fallback UX'i) | AC-4 |
| 4 | `max_tokens` parametresi API'ye geçersiz gelirse | API hata yanıtı (400/422 vb.) | MEVCUT exception-yakalama + fallback tetiklenir | Mesaj bir sonraki model/denemeyle işlenmeye devam eder | AC-5 |

Kısmi başarı: AC-4'te ele alındı — gerçekten çok rotalı bir mesaj cap'e
takılırsa, TÜM rotalar değil YARISI kaydedilmiş bir JSON'a düşer; bu
JSON'un parse edilemeyecek kadar bozuk olması (eksik parantez) BEKLENİR
ve mevcut fallback bunu bir sonraki modele/denemeye yönlendirir — "yarım
veri" asla sessizce kabul edilmez, ya TAM JSON ya da fallback.
Hiçbir şey yapılamadı ama hata da yok: Bu görev kapsamında yeni bir
durum eklenmiyor — mevcut "tüm modeller tükendi" davranışı (zaten
loglanıyor, `PARSE FAILED: All models exhausted`) korunuyor.
Boş sonuç ↔ hata ayrımı: Bu görev kapsamında değişmiyor.

## Test Strategy
Unit: 90% — `text_gen_parser.py`'nin 4 API çağrı noktasının her birinde
`max_tokens=1500` parametresinin isteğe dahil edildiğini doğrulayan
mock-tabanlı testler; kesilmiş JSON senaryosunda fallback'in tetiklendiğini
doğrulayan test.
Integration: 10% — Stage 1 → Stage 2 tam akışında cap'in her iki
aşamada da tutarlı şekilde uygulandığını doğrulayan bir test.
E2E: 0% — bu projede e2e altyapısı yok, gerçek API anahtarı gerektirir.

## Benchmark / Başarı Ölçütü
Coverage Target: 90%
Diğer ölçülebilir kriterler: Deploy sonrası 48 saatlik canlı gözlemde,
`data/ai_spend_history.json`'a yeni eklenen DeepSeek kayıtlarından
**1500+ output token'lı çağrı oranı %2'nin altında** olmalı (mevcut
durumda bu oran Ağustos'ta %79'du — `output >= 1500` filtreleniyor,
`>1000` değil, çünkü cap artık 1500'de kesiyor).

## Kapsam Dışı
- DeepSeek'in NEDEN runaway generation'a girdiğinin kök nedeninin
  araştırılması (prompt mühendisliği, `response_format` ayarları,
  belirli mesaj tipleriyle korelasyon vb.) — bu görev SADECE bir
  güvenlik ağı (cap) ekliyor, kök nedeni düzeltmiyor. Ayrı bir görev
  olarak ele alınabilir.
- Groq'un günlük limit/rate-limit sorunları — kullanıcı açıkça bu
  görevin kapsamı dışında bıraktı ("groqları boşver").
- DeepSeek hesabına otomatik bakiye yükleme (top-up) — sadece izleme
  (`deepseek-primary-balance-alert` görevinde zaten yapıldı), otomatik
  yükleme ayrı bir görev.
- `dedup-active-ids-fix` görevinde ele alınan tekrar-işleme sorunu —
  bu görevden bağımsız, zaten commit edildi.
- Model sırası (DeepSeek/Groq önceliği) — `deepseek-primary-balance-alert`
  görevinde ele alındı, bu görevin kapsamı dışında.

## Etkilenen Dosyalar/Modüller (bilinen)
- `text_gen_parser.py` — 4 API çağrı noktası (satır ~279, ~290, ~465, ~476).

## Rollback Beklentisi
`max_tokens` parametresinin kaldırılması (geri alınması) 4 satırlık bir
değişiklik — düşük riskli, mevcut fallback/hata mantığına dokunmuyor.
Geri alınırsa sistem eski (cap'siz) haline döner, maliyet riski geri gelir
ama fonksiyonel bir regresyon oluşmaz.

## Risks
- `max_tokens=1500` gerçekten 10+ rotalı bir mesajı kesip fallback'e
  düşürebilir — bu, veri kaybı DEĞİL, sadece bir sonraki modele/denemeye
  yönlendirme (mevcut fallback zaten JSON parse hatalarını bu şekilde
  ele alıyor). Nadir ve kabul edilebilir bir taviz.
- Cap, runaway'in KÖK NEDENİNİ çözmüyor — sistem hâlâ her runaway
  denemesinde 1500 tokene kadar (tam cap'e kadar) harcama yapacak,
  sadece bunun ÜST SINIRINI koyuyor. Kök neden ayrı bir görev.

## Assumptions
- DeepSeek ve Groq'un (OpenAI-uyumlu) API'leri `max_tokens` parametresini
  standart olarak destekliyor — (Haiku alt-ajanı tarafından yanıtlandı:
  ikisi de OpenAI SDK uyumlu client kullanıyor, `max_tokens` standart bir
  OpenAI Chat Completions parametresi).
- `max_tokens=1500` değeri, tipik 1-5 rotalı bir mesaj için yeterli
  güvenlik payı bırakıyor (Haiku alt-ajanı tarafından yanıtlandı: normal
  çağrı ~300-500 token ürettiği için 3-5x pay bırakır).

## Unknowns
- Gerçekte kaç mesajın 10+ rota içerdiği ve bu yüzden 1500 token cap'ine
  YAKLAŞABİLECEĞİ bilinmiyor — deploy sonrası canlı gözlemle netleşecek
  (AC-4/Benchmark).
- Runaway generation'ın kök nedeni (prompt, model davranışı, belirli
  mesaj içeriği ile korelasyon) bilinmiyor — kapsam dışı bırakıldı.

## Sorular ve Cevaplar (ham kayıt)
_Haiku alt-ajanı tarafından yanıtlandı (claude-omni kurulu değil, fallback kullanıldı):_
1. max_tokens cap değeri? → **1500 token** — tipik 1-5 rotalı JSON için 3-5x güvenlik payı, 40k runaway'i kesin durdurur.
2. Cap tüm modellere mi? → **Evet, 4 çağrı noktasının tümüne** — runaway riski model-agnostik.
3. Kesilmiş JSON'da ne olmalı? → **Mevcut fallback + `truncated_at_max_tokens` log** — JSON parse hatası zaten fallback'i tetikler, log tanı için eklendi.
4. Happy path çıktısı? → **~300-500 token, cap tetiklenmez, mevcut davranış korunur.**
5. Edge case (10+ rota)? → **Cap'e yaklaşabilir/takılabilir, takılırsa fallback.**
6. Edge case (runaway)? → **Cap keser, fallback tetiklenir + log.**
7. Başarı ölçütü? → **Post-deploy 48 saat, 1500+ token'lı çağrı oranı <%2** (Ağustos'ta %79'du).
8. Kapsam dışı mı kök neden? → **Evet, sadece güvenlik ağı ekleniyor, kök neden ayrı görev.**
9. Test stratejisi? → **Unit %90, Integration %10, E2E %0.**
10. Rollback? → **4 satır kod, düşük risk, fonksiyonel regresyon yok.**
