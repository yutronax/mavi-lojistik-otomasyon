---
task_slug: baileys-uretim-gecisi
jira_id: null
saga_task_id: 352
priority: critical
coverage_target: null
performance_target: null
memory_target: null
test_strategy:
  unit: 20
  integration: 70
  e2e: 10
affected_modules:
  - sidecar/bridge.js
  - src/fetchers/whapi_fetcher.py (devre dışı bırakılacak, silinmeyecek)
  - src/api/webhook_server.py
  - src/parsers/veri_cekici_ayristirici.py
---

# ATDD — baileys-uretim-gecisi

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga task #352 (epic #46 "Baileys — Tam kesim ve Whapi iptali", proje #8 "maviLojistik").

## ⚠️ KULLANICI KARARI (kayıt altına alınmış risk kabulü)
Orijinal geçiş planı, üretim numarasını riske atmadan önce epic #45'te
**2-4 haftalık paralel test/gözlem** öngörüyordu (Kritik öncelik —
ban riski öngörülemez, bazı hesaplar günler içinde bazıları aylarca
sorunsuz banlanmıyor). Kullanıcı bu süreci **bilerek atlamaya karar verdi**
— risk kendisine açıkça anlatıldı (`AskUserQuestion` ile "paralel test
süresini atla, aslı numarayı hemen Baileys'e geçir" seçeneği sunuldu, bunu
seçti). Bu ATDD, bu kararı **değiştirmiyor**, ama mühendislik açısından
makul olan tek bir güvenlik önlemini koruyor: **`whapi_fetcher.py` ve
Whapi aboneliği silinmiyor/iptal edilmiyor** — hızlı geri dönüş (rollback)
için bir süre paralel/pasif olarak kod tabanında kalıyor. Bu, "2-4 hafta
bekle" ile çelişmiyor — sadece "geri dönüş yolu açık kalsın" demek.

## Persona
İşletme sahibi/sistem operatörü — WhatsApp hesabının kontrolünü elinde tutan, geçişin riskini bilerek kabul eden kişi.

## Hedef (Neden)
Whapi.cloud aboneliğinin ($35/ay) maliyetini ortadan kaldırmak — asıl üretim WhatsApp numarasının mesaj kaynağını Whapi'den Baileys'e (`sidecar/bridge.js`) taşımak.

## User Story
As a işletme sahibi
I want asıl üretim numarasının Baileys üzerinden mesaj alıp işlemesini
So that Whapi.cloud aboneliğini iptal edip aylık $35 tasarruf edebileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `sidecar/bridge.js` hazır ve `webhook_server.py`'nin `/baileys-webhook` endpoint'i üretimde çalışıyor, When kullanıcı **asıl üretim numarasıyla** QR taratıp `bridge.js`'i üretim sunucusunda (sürekli çalışacak şekilde, örn. PM2/systemd ile) başlatırsa, Then gelen gerçek yük ilanı mesajları `orchestrator.add_to_processing_queue()`'ya ulaşır ve mevcut parser/YukBurada.com akışı hiç değişmeden çalışmaya devam eder.
2. [Critical] Given üretim numarası QR taratılırken numara zaten başka bir cihazda/WhatsApp Web'de aktifse, When taratma denenirse, Then taratma başarısız olur, açık bir hata gösterilir — "önce diğer bağlı cihazı/Web oturumunu kapatın" talimatı verilir; sessizce yarım bir bağlantı oluşturulmaz.
3. [Critical] Given geçiş sonrası `bridge.js` üretim sunucusunda çöker/sunucu yeniden başlarsa, When bu olursa, Then otomatik yeniden başlatma (PM2/systemd restart policy) devreye girer — süreç manuel müdahale beklemeden kendini toparlar.
4. [High] Given Whapi webhook/polling ile Baileys aynı anda aktif kalırsa (geçiş anındaki kısa çakışma penceresi), When aynı mesaj her iki kanaldan da gelirse, Then mevcut ID/body bazlı dedup mantığı (zaten `add_to_processing_queue`'da var, `data_service.is_id_handled`/`is_body_known`) mesajı **bir kez** işler — çift gönderim YukBurada.com'a gitmez.
5. [High] Given `bridge.js` üretimde çalışıyor görünüyor (process ayakta, `[BAGLANDI]` logu var) ama session sessizce bozulmuşsa (örn. WhatsApp tarafında görünmez bir kesinti), When 1+ saat hiç mesaj gelmezse, Then bu durum epic #44'ün `risk_check.js`/log'larından fark edilebilir olmalı — ama bu görev otomatik alarm KURMUYOR (kapsam dışı), sadece kullanıcının manuel kontrol edebileceği bir iz bırakıyor.
6. [Medium] Given geçiş sonrası ciddi bir sorun çıkarsa (mesajlar akmıyor, hesap banlandı), When kullanıcı geri Whapi'ye dönmek isterse, Then `whapi_fetcher.py` ve `webhook_server.py`'nin Whapi webhook kayıt (`setup_webhook`)/ngrok mantığı silinmediği için, `bridge.js`'i durdurup eski `run_server()` akışını (ngrok + Whapi webhook) yeniden başlatmak **5 dakikadan kısa sürede** mümkün olmalı.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path — QR taratıldı, bridge.js üretimde stabil çalışıyor | `add_to_processing_queue()` normal akış | Gerçek mesajlar işlenir, YukBurada.com'a gider | Normal operasyon, fark edilir bir değişiklik yok (kullanıcı için şeffaf) | AC-1 |
| 2 | QR taratma başarısız (numara başka yerde aktif) | Bağlantı kurulamaz | Yok | Açık hata: "numara başka bir cihazda WhatsApp Web'e bağlı, önce onu kapatın" | AC-2 |
| 3 | bridge.js çöker | Process restart policy devreye girer | Kısa bir kesinti penceresi (restart süresi kadar) | Loglarda `[BAGLANTI KAPANDI]` sonrası otomatik yeniden başlatma görülür | AC-3 |
| 4 | Whapi + Baileys aynı mesajı ikisi de gönderirse | İkinci gelen, dedup ile sessizce atlanır | Yok (tekilleştirme zaten var) | Log'da "zaten işlenmiş, atlandı" satırı, kullanıcı ekstra bir şey görmez | AC-4 |
| 5 | Sessiz arıza (bağlı görünüyor ama mesaj akmıyor) | Otomatik alarm YOK — bu görevin kapsamı dışı | Yok | `risk_check.js` çalıştırılırsa "1 saattir mesaj yok" gibi bir iz bırakır, otomatik bildirim yapılmaz | AC-5 |
| 6 | Kısmi başarı: bridge.js çalışıyor ama bazı mesaj tipleri (medya/reaction) işlenmiyor | `extractText()` `null` dönenler zaten `bridge_unhandled_messages.log`'a düşüyor (mevcut davranış) | Yok, sadece log | Metin dışı mesajlar log'da görülebilir, sessizce kaybolmaz | (mevcut davranış, bu görev değiştirmiyor) |

Kısmi başarı: Satır 6 — zaten var olan `bridge_unhandled_messages.log` mekanizması, bu görev onu değiştirmiyor sadece üretim trafiğinde de aynı şekilde çalıştığını doğruluyor.
Hiçbir şey yapılamadı ama hata da yok: **AC-5'in tam senaryosu bu** — bridge.js sağlıklı görünür ama session gerçekte kopmuşsa, sistem hiçbir hata vermez, sadece mesaj akışı durur. Bu görev bunu otomatik tespit etmiyor (kapsam dışı, gelecekte epic #44'ün risk aracına bir "son mesaj zamanı" alarm eklenmesi ayrı bir görev olabilir) — ama en azından `risk_check.js` ile MANUEL tespit edilebilir olması sağlanıyor.
Boş sonuç ↔ hata ayrımı: "Mesaj yok çünkü gerçekten sakin bir dönem" ile "mesaj yok çünkü session koptu" arasındaki fark bu görevde otomatik ayırt edilmiyor — kullanıcı `risk_check.js`'i çalıştırıp disconnect log'una bakarak kendisi ayırt etmeli.

## Test Strategy
Unit: 20% — `bridge.js`'in başlatma/config mantığı (üretim numarasına özel bir kod değişikliği yok, mevcut kod aynen kullanılıyor, bu yüzden unit oranı düşük).
Integration: 70% — Baileys session kurulumu, webhook endpoint'e gerçek POST, mesaj yönlendirme, dedup davranışı — bunların çoğu epic #42/43'te zaten test edildi, bu görev üretim numarasıyla TEKRAR doğruluyor.
E2E: 10% — üretim numarasından gerçek bir test mesajı gönderilip YukBurada.com'a kadar (veya en azından işlenmemiş kuyruğa kadar) ulaştığının doğrulanması + ilk saatlerde ağır manuel izleme (otomatik test değil, insan gözlemi).

## Benchmark / Başarı Ölçütü
Coverage Target: n/a (bu bir cutover görevi, yeni kod kapsamı sınırlı)
Performance Target: yok
Diğer ölçülebilir kriterler:
- En az birkaç saat boyunca Baileys üzerinden gerçek üretim mesajları sıfır kritik hatayla işlenmeli.
- Whapi'nin tarihsel teslimat oranıyla karşılaştırıldığında gözle görülür bir bozulma olmamalı (sayısal bir hedef konulamıyor çünkü Whapi'nin geçmiş oranı bu ATDD'de bilinmiyor — kullanıcı gözlemiyle değerlendirilecek).
- Whapi'den Baileys'e geçiş sırasında hiçbir mesajın çift işlenmediği (AC-4) doğrulanmalı.

## Kapsam Dışı
- `whapi_fetcher.py` dosyasının silinmesi — devre dışı bırakılacak (çağrılmayacak) ama kod tabanında kalacak, hızlı rollback için.
- Whapi.cloud aboneliğinin fiilen iptal edilmesi — bu görev sadece teknik geçişi yapıyor, abonelik iptali kullanıcının kendi kararı, birkaç gün/hafta gözlemledikten sonra ayrı bir adım.
- `whapi_fetcher.py`'yi çağıran TÜM dosyaların (health check, risk API, settings sayfası) güncellenmesi — sadece ANA mesaj çekme yolu (fetch_all_messages → orchestrator kuyruğu) Baileys'e taşınıyor. `get_channel_risk`/`calculate_channel_risk` (Whapi Safety Meter) gibi ikincil özellikler bu görevde dokunulmuyor (zaten epic #44'te Baileys tarafı için ayrı bir risk aracı yazıldı).
- Otomatik "sessiz arıza" alarmı (AC-5) — manuel tespit yeterli sayılıyor bu görevde.
- 24 saatlik zorunlu paralel gözlem penceresi eklenmesi — Haiku alt-ajanı bunu önerdi ama kullanıcının açık kararı "hemen geçiş" olduğu için ATDD'ye zorunlu bir AC olarak eklenmedi, sadece Assumptions'ta not düşüldü.

## Etkilenen Dosyalar/Modüller (bilinen)
- `sidecar/bridge.js` — üretim ortamında sürekli çalışır hale getirilecek (PM2/systemd config, kod değişikliği değil, dağıtım/operasyon değişikliği).
- `src/api/webhook_server.py` — `run_server()`'ın Whapi webhook/ngrok kaydı (`setup_webhook`) artık **çağrılmayacak** ama fonksiyon silinmeyecek (AC-6, rollback).
- `src/fetchers/whapi_fetcher.py` — `fetch_all_messages`/periyodik polling artık tetiklenmeyecek (orchestrator'ın periyodik döngüsünden çıkarılacak), ama dosya ve `get_channel_risk` gibi fonksiyonlar kalacak.
- `src/parsers/veri_cekici_ayristirici.py` — `run_loop()` (periyodik Whapi polling döngüsü) muhtemelen devre dışı bırakılacak — **plan aşamasında tam olarak nerede/nasıl kapatılacağı netleştirilecek (Unknown)**.

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu makinede git reposunun kökünün proje klasörüyle aynı olup olmadığı bu ATDD'de kontrol edilmedi. `plan` adımında Grep/Glob kullanılırken, arama proje worktree'siyle (`.claude/worktrees/festive-pare-2fb538`) sınırlı tutulacak, kök dizinden sınırsız arama yapılmayacak.

## Rollback Beklentisi
`whapi_fetcher.py` ve `webhook_server.py`'nin Whapi webhook/ngrok mantığı silinmediği için, ciddi bir sorun çıkarsa: `bridge.js` durdurulur, `webhook_server.py`'nin eski `run_server()` akışı (ngrok tüneli + Whapi webhook kaydı) yeniden başlatılır. Bu, kod değişikliği gerektirmeden, sadece hangi sürecin çalıştırıldığına bağlı bir operasyonel geri dönüş — teorik olarak 5 dakikadan kısa sürmeli (AC-6).

## Risks
- **Ana risk (kullanıcı tarafından bilerek kabul edildi):** Üretim numarası hiç test edilmemiş bir Baileys sürümüyle karşı karşıya, ban riski öngörülemez.
- Whapi ile Baileys'in geçiş anında kısa süre paralel çalışması, çift mesaj işleme riski yaratabilir (AC-4 ile azaltılıyor, dedup zaten var).
- `veri_cekici_ayristirici.py`'nin periyodik Whapi polling döngüsünün (`run_loop`) tam olarak nerede kapatılacağı henüz netleşmedi — yanlış yerden kapatılırsa hem Whapi hem Baileys aynı anda aktif kalabilir (plan aşamasında netleştirilecek).

## Assumptions
- (Haiku alt-ajanı önerisi, kullanıcı kararıyla ÇATIŞMIYOR ama zorunlu AC yapılmadı) İlk birkaç saat/gün boyunca kullanıcının manuel olarak (kendi başına, epic #45 gibi zorunlu bir süreç değil) izleme yapması önerilir.
- `bridge.js`'in üretim sunucusunda PM2/systemd gibi bir süreç yöneticisiyle çalıştırılacağı varsayılıyor (AC-3) — kullanıcı onaylamadıysa bu bir varsayım, plan aşamasında netleştirilmeli.
- Üretim numarasının şu anda başka bir cihazda WhatsApp Web'e bağlı olmadığı varsayılıyor — QR taratma anında doğrulanacak (AC-2).

## Unknowns
- `veri_cekici_ayristirici.py`'nin Whapi polling döngüsünün (`run_loop`) tam olarak hangi satırda/nasıl devre dışı bırakılacağı — plan aşamasında kod okunarak netleştirilecek.
- `bridge.js`'in üretim sunucusunda hangi süreç yöneticisiyle (PM2, systemd, Windows Service) çalıştırılacağı — sunucunun işletim sistemine bağlı, plan aşamasında netleştirilecek.
- Whapi'nin geçmiş teslimat oranı (kaç mesajın kaçırıldığı/gecikmediği) bilinmiyor — bu ATDD'de sayısal bir karşılaştırma hedefi konulamadı, kullanıcı gözlemine bırakıldı.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü/persona → İşletme sahibi/sistem operatörü. (Haiku alt-ajanı tarafından yanıtlandı)
2. Ana hedef/neden → Maliyet tasarrufu $35/ay. (kullanıcı mesajından, tekrar sorulmadı)
3. Happy path senaryosu → QR taratma → bridge.js üretimde başlatma → (Haiku'nun önerdiği zorunlu 24 saat gözlem AC yapılmadı, kullanıcı kararıyla çelişiyordu) → whapi_fetcher.py arşivlenir (silinmez). (Haiku alt-ajanı tarafından yanıtlandı, 24 saat kısmı Assumptions'a taşındı)
4. Edge case 1 (QR taratma başarısız) → Numara başka cihazda aktifse önce onu kapat. (Haiku alt-ajanı tarafından yanıtlandı)
5. Edge case 2 (bridge.js çöker) → Otomatik restart policy (PM2/systemd). (Haiku alt-ajanı tarafından yanıtlandı)
6. Davranış sözleşmesi (whapi_fetcher çağrı noktaları) → Sadece ana mesaj çekme yolu değişiyor, health/risk/settings gibi ikincil çağrılar bu görevde dokunulmuyor. (Haiku alt-ajanı tarafından yanıtlandı, ATDD'de netleştirildi)
7. Başarı ölçütü → Birkaç saat sıfır kritik hata, çift mesaj yok. (Haiku alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → whapi_fetcher.py silinmeyecek, abonelik iptal edilmeyecek, ikincil çağrılar değişmeyecek. (Haiku alt-ajanı tarafından yanıtlandı)
9. Bağımlılıklar → whapi_fetcher.py, webhook_server.py, veri_cekici_ayristirici.py, bridge.js. (Haiku alt-ajanı tarafından yanıtlandı)
10. Rollback beklentisi → <5 dakika, whapi_fetcher.py silinmediği için. (Haiku alt-ajanı tarafından yanıtlandı)
11. Kabul kriteri sahibi → İşletme sahibi. (Haiku alt-ajanı tarafından yanıtlandı)
12. Test stratejisi → %20 unit / %70 integration / %10 e2e. (Haiku alt-ajanı tarafından yanıtlandı)
