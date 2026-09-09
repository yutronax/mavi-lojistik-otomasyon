---
task_slug: deepseek-balance-diff-maliyet-hesaplama
jira_id: null
saga_task_id: 374
priority: high
coverage_target: 80
performance_target: null
memory_target: null
test_strategy:
  unit: 70
  integration: 20
  e2e: 10
affected_modules:
  - src/api/admin_panel.py
  - data/deepseek_balance_history.json (yeni)
---

# ATDD — deepseek-balance-diff-maliyet-hesaplama

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #374 (epic #51 "AI Maliyet
İzleme ve Doğruluğu", proje: maviLojistik).

## Persona
Sistem operatörü (kullanıcının kendisi) — admin panelden DeepSeek API
maliyetini izliyor, panelde gösterilen harcama rakamlarına güvenmek
istiyor.

## Hedef (Neden)
`data/ai_spend_history.json`, her AI çağrısından dönen
`usage.prompt_tokens`/`completion_tokens` değerlerinin yerel bir fiyat
tablosuyla çarpılmasıyla hesaplanan bir TAHMİN. Kullanıcı bu tahminin
gerçek DeepSeek faturasından (~5x) saptığını gözlemledi (ayrı ve bu
görevden BAĞIMSIZ bir investigation task'ı — bkz.
`obss_project/artifacts/deepseek-saatlik-sabit-maliyet-kaynagi/` — kök
nedeni araştırıyor). Bu görev kök nedeni beklemeden, doğrudan DAHA DOĞRU
bir veri kaynağına geçiyor: `admin_panel.py`'de zaten var olan
`_check_deepseek_balance_once()` / `_refresh_deepseek_balance()` 15
dakikalık poller'ı, DeepSeek'in kendi `/user/balance` uç noktasından
okuduğu bakiyeyi sadece cache'liyor (son değer, geçmiş tutulmuyor). Bu
görev, ardışık iki bakiye okuması arasındaki FARKI ("önceki_bakiye -
şimdiki_bakiye") gerçek harcama olarak persist eden bir mekanizma ekliyor
— DeepSeek'in kendi faturalandırdığı rakam, token×fiyat tahmini değil.

## User Story
As a sistem operatörü
I want DeepSeek harcamasının token×fiyat tahmini yerine gerçek bakiye
düşüşüne (balance-diff) dayalı hesaplanmasını
So that admin panelde gördüğüm maliyet rakamlarına güvenebileyim ve
gerçek faturayla örtüşen bir veri kaynağım olsun

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `_refresh_deepseek_balance()` döngüsünün ardışık iki
   başarılı okuması (t1: balance=$10.00, t2: balance=$9.75), When t2
   okuması tamamlanır, Then fark ($0.25) "t1→t2 arası gerçek harcama"
   olarak `data/deepseek_balance_history.json`'a bir kayıt (timestamp
   çifti + fark + iki ham balance değeri) olarak eklenir (append).
2. [Critical] Given ardışık iki okuma arasında balance ARTMIŞ (ör.
   $9.75 → $12.00, top-up/yeniden yükleme), When fark hesaplanır, Then
   negatif fark asla "harcama" olarak yazılmaz — o pencere için
   harcama=0 kaydedilir VE kayda `"top_up_detected": true` alanı eklenir.
3. [Critical] Given bir okuma "unknown"/ağ hatası döner (mevcut
   `_check_deepseek_balance_once`'ın except bloğu), When bu pencere
   için fark hesaplanacaksa, Then o pencere harcama=0 YAZILMAZ — bunun
   yerine `"gap": true` ile "veri yok" olarak işaretlenir, ve bir
   SONRAKİ başarılı okuma en son BİLİNEN başarılı balance değeriyle
   karşılaştırılır (ara okumaların kaybı fark hesaplamasını bozmaz).
4. [High] Given ilk hiç okuma yapılmamış durum (ilk poll, karşılaştırılacak
   önceki değer yok), When ilk `_check_deepseek_balance_once` başarıyla
   döner, Then hiçbir fark/harcama kaydı YAZILMAZ — sadece ilk balance
   "referans" olarak saklanır (harcama=0 veya boş kayıt YAZILMAZ, çünkü
   henüz karşılaştırma yapılamaz).
5. [Medium] Given `/status` endpointi, When çağrılır, Then mevcut
   `deepseek_balance` alanına ek olarak yeni bir alan (ör.
   `deepseek_real_spend`: son bilinen balance-diff bazlı harcama, ör. son
   24 saatlik toplam) döner — mevcut `ai_spend_history.json` tabanlı
   alanlar DEĞİŞTİRİLMEZ, ikisi paralel gösterilir.

## Davranış Sözleşmesi (hangi durumda ne döner)
Bu bir arkaplan hesaplama mekanizması — kullanıcı girdisi veya yeni bir
HTTP endpoint yok, tek temas noktası mevcut `/status` endpointinin
genişletilmesi. Standart CRUD tablosu yerine, poller'ın olası durumları:

| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: iki ardışık başarılı okuma, balance azalmış | N/A (arkaplan) | `deepseek_balance_history.json`'a `{t1, t2, prev_balance, curr_balance, spend: fark}` eklenir | `/status`'ta `deepseek_real_spend` güncellenir | AC-1 |
| 2 | Balance artmış (top-up) | N/A | Kayıt `spend: 0, top_up_detected: true` ile eklenir | Panelde harcama 0 görünür, negatif harcama ASLA gösterilmez | AC-2 |
| 3 | Okuma "unknown" (ağ hatası/timeout) | N/A | Kayıt `gap: true` ile eklenir, spend hesaplanmaz; bir sonraki başarılı okuma en son bilinen başarılı değerle karşılaştırılır | Panelde o pencere için "veri yok" / boşluk olarak yansır, 0 harcama YAZILMAZ | AC-3 |
| 4 | İlk okuma (referans yok) | N/A | Hiçbir kayıt eklenmez, sadece iç referans güncellenir | Panelde henüz `deepseek_real_spend` verisi yok (null/boş) | AC-4 |
| 5 | Kısmi başarı: history dosyasına yazma başarısız (disk/izin hatası) | N/A | Hata loglanır (`logger.error`), in-memory referans yine de güncellenir (bir sonraki karşılaştırma için) | Panelde o pencere kaybolur ama sistem çökmez | AC-1 (dayanıklılık notu) |
| 6 | Hiçbir şey yapılamadı ama hata yok (poller hiç çalışmamış, `DEEPSEEK_API_KEY` yok) | N/A | Mevcut davranış korunur — `_refresh_deepseek_balance` zaten `if not api_key: return` ile sessizce çıkıyor | `/status`'ta `deepseek_real_spend: null` | AC-5 |

Yetkisiz erişim: N/A — bu iç bir poller, dış istemciden gelen bir istek
yok; DeepSeek API key zaten env'den okunuyor, yetkilendirme hatası
DeepSeek'in kendi 401 yanıtı olarak mevcut `except Exception` bloğunda
"unknown" durumuna düşer (satır 5 ile aynı davranış).
Zaman aşımı: mevcut `urlopen(..., timeout=10)` ile aynı — "unknown"
durumuna düşer (satır 3 ile aynı davranış, ayrı bir dal değil).

Boş sonuç ↔ hata ayrımı: `gap: true` (ağ hatası → "bilinmiyor") ile
`spend: 0, top_up_detected: false` (gerçekten hiç harcama olmamış, balance
hiç değişmemiş) AÇIKÇA farklı alanlarla ayrılır — ikisi de "0 harcama"
gibi görünmez.

## Test Strategy
Unit: 70% — fark hesaplama fonksiyonu (pozitif fark → spend, negatif
fark → top_up_detected, ilk okuma → hiç kayıt yok, "unknown" sonrası
gap işaretleme ve sıradaki karşılaştırmanın en son bilinen değeri
kullanması)
Integration: 20% — `_refresh_deepseek_balance` döngüsünün gerçek zamanlı
olmayan (mock'lanmış zamanlayıcı) çalışmasıyla history dosyasına doğru
sırayla append yapması, dosya yazma hatası durumunda sistemin çökmemesi
E2E: 10% — gerçek DeepSeek API'ye çağrı maliyetli ve gereksiz; mock'lanmış
HTTP yanıtlarıyla `/status` endpointinin yeni alanı doğru döndürdüğünün
uçtan uca testi

## Benchmark / Başarı Ölçütü
Coverage Target: 80%
Performance Target: yok (mevcut 15dk polling aralığı korunuyor, ek I/O
ihmal edilebilir)
Memory: yok
Diğer ölçülebilir kriterler:
- Balance-diff bazlı günlük toplam harcama, DeepSeek'in kendi
  dashboard'undaki gerçek faturanın ±%10'u içinde olmalı (teorik olarak
  aynı kaynak olduğu için sapma sıfıra yakın beklenir — kabul kriteri
  onayı kullanıcının kendi canlı gözlemine kalıyor, kod dışı doğrulama).
- Kabul kriteri onayı: kullanıcı + otomatik testler (mock'lu). Gerçek
  DeepSeek dashboard karşılaştırması VPS'te canlı gözlemle yapılacak,
  bu ortamda doğrulanamaz.

## Kapsam Dışı
- Mevcut `data/ai_spend_history.json` (token×fiyat tahmini) SİLİNMEZ —
  iki kaynak paralel tutulur, karşılaştırma/geçiş dönemi için.
- `obss_project/artifacts/deepseek-saatlik-sabit-maliyet-kaynagi/` kök
  neden investigation'ı — bu görev ondan tamamen BAĞIMSIZ.
- DeepSeek dışındaki modellerin (Gemini, Groq) maliyet hesaplaması.
- 15 dakikalık poll aralığının kısaltılması/değiştirilmesi — bilinen bir
  sınırlama olarak not düşülüyor (bkz. Unknowns), bu görevde
  DEĞİŞTİRİLMİYOR.
- VPS'e gerçek deploy ve orada canlı doğrulama — kod bu ortamda yazılır,
  gerçek fatura karşılaştırması kullanıcının kendi gözlemine kalıyor.
- DeepSeek'in başarısız/rate-limit çağrıları faturalandırıp
  faturalandırmadığı sorusu — bu, balance-diff yaklaşımının doğası gereği
  zaten otomatik olarak doğru yansır (DeepSeek ne faturalandırırsa bakiye
  o kadar düşer), ayrıca araştırılmıyor.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` (satır 221-273: `_check_deepseek_balance_once`,
  `_refresh_deepseek_balance`, `/status` handler, `_deepseek_balance_cache`)
- `data/deepseek_balance_history.json` (YENİ dosya — ardışık okumaları ve
  hesaplanan farkları persist eder; `data/ai_spend_history.json`'a
  dokunulmaz)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu görevin `plan` adımından önce `git rev-parse
--show-toplevel` ile proje kökü tekrar doğrulanmalı; arama maviLojistik
worktree kökü ile sınırlı tutulmalı.

## Rollback Beklentisi
Additive bir değişiklik — mevcut `ai_spend_history.json` ve mevcut
`/status` alanları DEĞİŞMİYOR, sadece yeni bir dosya ve yeni bir alan
ekleniyor. Hata durumunda `git revert` yeterli, veri kaybı riski yok.

## Risks
- Proje tek DeepSeek hesabı/tek API key kullanıyor varsayımı — eşzamanlı
  başka bir process/kullanıcı aynı hesaptan harcama yaparsa balance-diff
  o harcamayı da (yanlışlıkla bu projenin harcamasıymış gibi) sayar.
- 15 dakikalık poll aralığının kısa süreli yoğun harcama patlamalarını
  (ör. 2 dakikada belirgin harcama) yeterince hassas yakalayıp
  yakalamadığı bilinmiyor — bu aralık bu görevde değiştirilmiyor.
- `_deepseek_balance_cache`'in mevcut yapısı (sadece son değer) yerine
  history dosyasına geçişte, uygulamanın yeniden başlatılması durumunda
  "önceki bilinen balance" referansının disk'ten okunması gerekecek
  (in-memory referans süreç yeniden başlarsa kaybolur) — bu, ilk
  okumanın "referans yok" (AC-4) durumuna düşmesine neden olabilir,
  kabul edilebilir bir sınırlama olarak işaretleniyor.

## Assumptions
- Proje tek DeepSeek hesabı/tek API key kullanıyor, eşzamanlı başka bir
  process/kullanıcı aynı hesaptan harcama yapmıyor.
- Mevcut `_check_deepseek_balance_once`'ın timeout/401/ağ hatası
  davranışları (hepsi "unknown" dönüyor) bu görevde DEĞİŞTİRİLMİYOR,
  sadece "unknown" sonucunun balance-diff hesaplamasına nasıl yansıdığı
  (gap olarak) ekleniyor.

## Unknowns
- 15 dakikalık poll aralığının hassasiyeti yeterli mi, yoksa
  kısaltılması mı gerekiyor — bu görev kapsamında karar VERİLMİYOR.
- Süreç yeniden başlatıldığında (PM2 restart vb.) "önceki bilinen
  balance" referansının history dosyasından nasıl kurtarılacağı — plan
  adımında netleştirilmeli (muhtemelen dosyadaki son kaydı okuyup
  referans olarak kullanmak).

## Sorular ve Cevaplar (ham kayıt)
1. Persona → Sistem operatörü/kullanıcının kendisi, admin panelden
   maliyet izliyor (Sonnet 5 low alt-ajanı tarafından yanıtlandı: mevcut
   mekanizma zaten aynı tüketiciye hizmet ediyor)
2. Ana hedef/neden → Token×fiyat tahmini gerçek faturadan sapıyor, panel
   rakamlarına güvenilemiyor (Sonnet 5 low alt-ajanı tarafından
   yanıtlandı: kullanıcının orijinal isteği ve bilinen ~5x sapma)
3. Happy path → t1/t2 ardışık okuma, fark = gerçek harcama, yeni dosyaya
   append (Sonnet 5 low alt-ajanı tarafından yanıtlandı: mevcut 15dk
   döngüsü doğal ölçüm penceresi)
4. Edge case (balance arttı/top-up) → spend=0 + top_up_detected flag'i,
   negatif harcama asla gösterilmez (Sonnet 5 low alt-ajanı tarafından
   yanıtlandı: risk analizinde zaten tanımlı en güvenli varsayılan)
5. Edge case (okuma hatası/unknown) → gap=true, spend yazılmaz, sıradaki
   okuma en son bilinen değerle karşılaştırılır (Sonnet 5 low alt-ajanı
   tarafından yanıtlandı: veri bütünlüğünü korumanın tek doğru yolu)
6. Davranış sözleşmesi → N/A (arkaplan mekanizması, dış girdi/endpoint
   yok), sadece `/status` genişletiliyor (Sonnet 5 low alt-ajanı
   tarafından yanıtlandı)
7. Başarı ölçütü → balance-diff toplamı gerçek faturanın ±%10'u içinde,
   coverage %80 (Sonnet 5 low alt-ajanı tarafından yanıtlandı: aynı
   kaynak olduğu için sapma sıfıra yakın beklenir)
8. Kapsam dışı → mevcut tahmin silinmez (paralel tutulur), kök-neden
   investigation'ı ayrı, diğer modeller, poll aralığı değişikliği, VPS
   canlı doğrulama (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → admin_panel.py (ilgili fonksiyonlar), yeni
   deepseek_balance_history.json, ai_spend_history.json'a dokunulmaz
   (Sonnet 5 low alt-ajanı tarafından yanıtlandı: mevcut veriyi bozmama)
10. Performans/güvenlik kısıtı → yok, mevcut mimari korunuyor (Sonnet 5
    low alt-ajanı tarafından yanıtlandı)
11. Rollback → git revert yeterli, additive değişiklik, veri kaybı riski
    yok (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
12. Kabul kriteri sahibi → kullanıcı + otomatik testler, gerçek fatura
    karşılaştırması kullanıcının canlı gözlemine kalıyor (Sonnet 5 low
    alt-ajanı tarafından yanıtlandı)
13. Test stratejisi → 70/20/10, hesaplama mantığı unit ağırlıklı (Sonnet
    5 low alt-ajanı tarafından yanıtlandı: saf fonksiyon mantığı)
14. Riskler/varsayımlar → tek hesap/tek API key varsayımı, poll
    aralığının hassasiyeti bilinmiyor ama bu görevde değiştirilmiyor
    (Sonnet 5 low alt-ajanı tarafından yanıtlandı)
