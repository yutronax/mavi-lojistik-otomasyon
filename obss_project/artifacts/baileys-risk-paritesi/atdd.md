---
task_slug: baileys-risk-paritesi
jira_id: null
saga_task_id: 351
priority: high
coverage_target: 75
performance_target: null
memory_target: null
test_strategy:
  unit: 75
  integration: 20
  e2e: 5
affected_modules:
  - sidecar/bridge.js
  - sidecar/risk_check.js (yeni)
  - src/utils/human_behavior.py (referans, değişmeyecek)
---

# ATDD — baileys-risk-paritesi

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #351 (epic #44 "Baileys — Risk paritesi (Safety Meter yerine)", proje #8 "maviLojistik").

## Persona
Proje sahibi/sistem operatörü — günlük veya kritik gönderim serilerine başlamadan önce hesabın ban riskini kabaca kontrol etmek istiyor.

## Hedef (Neden)
Whapi.cloud'un "Safety Meter" (`riskOfBlocking`) API'si, WhatsApp hesabının ban riskini 3 metrikle (riskFactor, riskFactorContacts, riskFactorChats, lifeTime) skorluyordu — bu, `tools/check_whatsapp_risk.py` üzerinden kullanıcıya erken uyarı veriyordu. Baileys'e geçildiğinde bu API'nin **doğrudan karşılığı yok** (WhatsApp resmi bir ban-risk skoru açıklamıyor, Whapi'ninki kendi iç tahminiydi). Bu görevin amacı: gerçek bir ban tahmini DEĞİL, ama Baileys'in kendi bağlantısından **gözlemlenebilir** proxy sinyalleri (disconnect sıklığı/tipi, mesaj hacmi, session sağlığı) toplayıp Whapi'nin raporuna benzer, aynı üç-seviyeli (Low/Medium/High) bir özet gösteren bir araç üretmek — "hiç risk sinyali yok" durumundan daha iyi bir gösterge sağlamak.

## User Story
As a proje sahibi
I want Baileys bağlantısının gözlemlenebilir sağlık/risk sinyallerini özetleyen bir komut
So that Whapi'nin Safety Meter'ı olmadan da ban riskine dair kaba bir erken uyarı alabileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `sidecar/bridge.js` bir süre çalışmış ve `connection.update` event'lerini logladıysa, When kullanıcı `node sidecar/risk_check.js` çalıştırırsa, Then son N saatteki disconnect sayısı/tipi (401/440/515 vb.), tahmini mesaj hacmi ve genel bir risk seviyesi (Low/Medium/High) komut satırına yazdırılır.
2. [Critical] Given hiçbir disconnect/mesaj verisi toplanmamışsa (yeni session, `<1 saat`), When `risk_check.js` çalıştırılırsa, Then risk seviyesi "Bilinmiyor/Veri Toplanıyor" olarak gösterilir — asla "Low" (güvenli) diye YANLIŞ bir güven verilmez.
3. [High] Given son 1 saatte 5+ kez 401/440/515 tipi disconnect olduysa, When risk hesaplanırsa, Then seviye "High" olarak işaretlenir ve kullanıcıya "işlemleri durdur, session'ı gözden geçir" önerisi gösterilir.
4. [High] Given disconnect verisi var ama mesaj hacmi verisi eksikse (örn. sidecar'ın mesaj sayacı hiç çalışmadıysa), When risk hesaplanırsa, Then bu **kısmi veri** olarak açıkça işaretlenir (hangi metriğin eksik olduğu belirtilir) — eksik metrik sanki "0/güvenli" gibi sessizce yutulmaz.
5. [Medium] Given kullanıcı `risk_check.js`'i bridge.js hiç çalıştırılmamışken çalıştırırsa, When log dosyası/veri kaynağı bulunamazsa, Then açık bir hata mesajı ("bridge.js hiç çalıştırılmamış, veri yok") verilir — boş/varsayılan bir risk skoru UYDURULMAZ.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path — stabil bağlantı, az disconnect (<2/gün), normal hacim | Risk: Low | Yok (salt okunur) | "✅ Risk: LOW — son 7 günde X disconnect, hesap stabil görünüyor" | AC-1 |
| 2 | Yetersiz veri (session <1 saat, hiç geçmiş kayıt yok) | Risk: Bilinmiyor/Unknown | Yok | "❓ Veri henüz toplanıyor — en az 1 saat çalıştırıp tekrar deneyin" | AC-2 |
| 3 | Sık disconnect (1 saatte 5+ kez 401/440/515) | Risk: High | Yok | "🔴 Risk: HIGH — Xx disconnect son 1 saatte, işlemleri durdurmanız önerilir" | AC-3 |
| 4 | Kısmi veri (disconnect var, mesaj hacmi yok) | Risk: Medium (eksik metrik açıkça belirtilerek) | Yok | "🟡 Risk: MEDIUM (kısmi veri — mesaj hacmi ölçülemedi, sadece bağlantı sağlığına göre)" | AC-4 |
| 5 | Veri kaynağı hiç yok (bridge.js hiç çalıştırılmamış) | Hata, risk hesaplanmaz | Yok | "❌ Hata: log dosyası bulunamadı — önce sidecar/bridge.js'i çalıştırın" | AC-5 |

Kısmi başarı: Satır 4 — bir metrik eksikken diğeriyle kaba bir skor üretilir ama bu "eksik veriyle hesaplandı" diye işaretlenir, tam veriliymiş gibi sunulmaz.
Hiçbir şey yapılamadı ama hata da yok: Bu araç salt-okunur bir raporlama aracı olduğu için "hiçbir şey yapılamadı" senaryosu satır 5'teki "veri kaynağı yok" hatasına denk düşüyor — sessizce boş/varsayılan bir rapor ASLA üretilmez, her zaman ya bir skor ya açık bir hata döner.
Boş sonuç ↔ hata ayrımı: "Veri yok, henüz toplanıyor" (AC-2, meşru — sistem yeni başladı) ile "veri kaynağı hiç bulunamadı" (AC-5, muhtemelen bridge.js hiç çalıştırılmadı) ayrı mesajlarla ayrılır — ikisi de "bilinmiyor" gibi görünmesin diye.

## Test Strategy
Unit: 75% — risk hesaplama mantığı (disconnect sayma, seviye belirleme, eksik-metrik işaretleme) — sabit/mock log verisiyle test edilebilir, gerçek WhatsApp bağlantısı gerektirmez.
Integration: 20% — `bridge.js`'in disconnect event'lerini gerçekten bir log dosyasına yazdığının ve `risk_check.js`'in bu dosyayı doğru okuduğunun doğrulanması.
E2E: 5% — gerçek bir Baileys bağlantısı üzerinden uçtan uca (maliyetli/pahalı, gerçek WhatsApp session'ı gerektirir, sınırlı tutulur).

## Benchmark / Başarı Ölçütü
Coverage Target: %75 (unit testler için)
Performance Target: yok
Diğer ölçülebilir kriterler:
- Proxy metrikler ölçülebilir olmalı: (a) bağlantı uptime oranı (%), (b) saatlik disconnect sayısı, (c) beklenmeyen logout (401) sayısı.
- Gerçek ban verisiyle doğrudan karşılaştırma yapılamaz (WhatsApp bunu açıklamıyor) — bu araç "kanıtlanmış doğru" değil, "mevcut sinyallerden en iyi tahmin" olarak konumlandırılmalı ve bu README'de açıkça belirtilmeli.

## Kapsam Dışı
- Gerçek ban tahmini / makine öğrenmesi modeli — sadece gözlemlenebilir sinyalleri raporlamak kapsamda, tahmin üretmek değil.
- Whapi'nin Safety Meter'ıyla birebir sayısal karşılaştırma/doğrulama — imkansız, farklı veri kaynakları.
- `human_behavior.py`'nin davranış simülasyon mantığının değiştirilmesi — bu görev sadece YENİ bir gösterge ekliyor, mevcut davranış kısıtlamalarına dokunmuyor.
- Otomatik aksiyon alma (örn. riski görünce otomatik olarak mesaj göndermeyi durdurma) — bu araç sadece raporlar, karar kullanıcının.

## Etkilenen Dosyalar/Modüller (bilinen)
- `sidecar/bridge.js` — disconnect event'lerini (statusCode, zaman damgası) bir log dosyasına yazacak şekilde genişletilecek (mevcut `[BAGLANTI KAPANDI]` konsol log'u zaten var, dosyaya da yazılması gerekiyor).
- `sidecar/risk_check.js` (yeni) — log dosyasını okuyup risk seviyesini hesaplayıp yazdıran CLI script.
- `src/utils/human_behavior.py` — sadece referans/ilham, değiştirilmeyecek.

## Rollback Beklentisi
Bu araç salt-okunur bir raporlama aracı — veri yazmıyor (disconnect log'u hariç, o da sadece ek/append, üzerine yazma yok). Hata durumunda geri alınacak bir işlem yok.

## Risks
- Baileys'in disconnect event'lerinin ne kadar güvenilir/eksiksiz loglandığı henüz doğrulanmadı (bridge.js şu an sadece konsola yazıyor, dosyaya değil) — bu görev bunu ekleyecek.
- Bu heuristiğin gerçek ban riskiyle ne kadar korelasyonlu olduğu bilinemez (WhatsApp resmi veri paylaşmıyor) — araç "kesin" değil "en iyi tahmin" olarak sunulmalı, kullanıcıyı yanlış güvene sevk etmemeli.
- @lid JID'leri (epic #43'te keşfedildi) — "bilinmeyen kişilerle etkileşim oranı" gibi bir metrik eklenirse, numara bazlı karşılaştırma @lid'li kişileri yanlış sınıflandırabilir. Bu görevde böyle bir metrik eklenmeyecek (Kapsam Dışı'na yakın, ama Risk olarak not düşülüyor).

## Assumptions
- (Haiku alt-ajanı önerisi) Kullanıcı bu aracı günde bir veya kritik işlem öncesi manuel çalıştıracak — otomatik/periyodik değil, bu görevin kapsamında değil.
- (Haiku alt-ajanı önerisi) 3 seviyeli (Low/Medium/High) sistem, Whapi'nin 3-seviyeli sistemine (İYİ/DİKKAT/TEHLİKE) benzerlik için tercih edildi — kullanıcı zaten bu formata alışkın.
- Disconnect log'unun tutulacağı süre penceresi netleşmedi (Haiku "son 7 gün" ve "son 1 saat" karışık kullandı) — plan aşamasında netleştirilecek (Unknown).

## Unknowns
- Disconnect log'unun ne kadar süre saklanacağı / rotasyon politikası — plan aşamasında netleştirilecek.
- `risk_check.js`'in log dosyasının tam yolu/formatı (JSON lines mı, tek JSON dosyası mı) — plan aşamasında kodda karar verilecek.
- Mesaj hacmi metriğinin nasıl toplanacağı (bridge.js zaten her mesajı `[WEBHOOK OK]` ile logluyor — bu sayılabilir mi, yoksa ayrı bir sayaç mı gerekiyor) — plan aşamasında netleştirilecek.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü/persona → Proje sahibi/sistem operatörü, günlük/periyodik sağlık kontrolü. (Haiku alt-ajanı tarafından yanıtlandı)
2. Ana hedef/neden → Ban riskini erken tespit etmek, gerçek tahmin değil gözlemlenebilir sinyal raporlama. (Haiku alt-ajanı tarafından yanıtlandı)
3. Happy path senaryosu → CLI komutu, risk seviyesi + disconnect + hacim özeti, Whapi raporuna benzer format. (Haiku alt-ajanı tarafından yanıtlandı)
4. Edge case 1 (veri yok) → "Insufficient Data" nötr seviye. (Haiku alt-ajanı tarafından yanıtlandı, ATDD'de "Bilinmiyor/Veri Toplanıyor" olarak netleştirildi)
5. Edge case 2 (sık disconnect) → High risk, session sağlığı sinyali. (Haiku alt-ajanı tarafından yanıtlandı)
6. Davranış sözleşmesi → 3 seviye (Low/Medium/High), her seviyede eylem önerisi. (Haiku alt-ajanı tarafından yanıtlandı)
7. Başarı ölçütü → Uptime %, disconnect sayısı, unexpected logout sayısı proxy metrikleri. (Haiku alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → ML/tahmin modeli kesinlikle kapsam dışı. (Haiku alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → bridge.js connection event'leri, human_behavior.py referans. (Haiku alt-ajanı tarafından yanıtlandı)
10. Rollback → Gerekli değil, salt okunur. (Haiku alt-ajanı tarafından yanıtlandı)
11. Kabul kriteri sahibi → Proje sahibi. (Haiku alt-ajanı tarafından yanıtlandı)
12. Test stratejisi → %75 unit / %20 integration / %5 e2e, gerekçe: hesaplama mantığı test edilebilir, canlı WhatsApp testi pahalı/sınırlı. (Haiku alt-ajanı tarafından yanıtlandı)
