---
task_slug: gruplar-tab-ui-yenileme
jira_id: null
saga_task_id: 364
priority: medium
coverage_target: 50
performance_target: null
memory_target: null
test_strategy:
  unit: 15
  integration: 15
  e2e: 70
affected_modules:
  - src/api/admin_panel.py
---

# ATDD — gruplar-tab-ui-yenileme

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga #364 altında takip ediliyor.

## Persona
Sistem operatörü (kullanıcı) — admin panelin "Gruplar" sekmesini
kullanarak WhatsApp gruplarını yönetiyor, mevcut sade görünümü daha
okunaklı ve profesyonel bulmuyor.

## Hedef (Neden)
Kullanıcı, kendi tasarım becerisine güvenmediğini belirtip v0 (Vercel'in
AI tasarım aracı) ile "Gruplar" sekmesi için bir tasarım ürettirdi ve
sonucu bir Artifact üzerinden inceleyip onayladı. Bu görev, onaylanan
tasarımı gerçek Flask admin paneline uygulayarak ekranı daha okunaklı ve
profesyonel hale getiriyor — mevcut işlevsellik korunarak.

## User Story
As a sistem operatörü
I want "Gruplar" sekmesinin daha okunaklı, aranabilir ve görsel olarak net
bir tasarıma sahip olmasını
So that kayıtlı/eklenmemiş grupları daha kolay yönetebileyim

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `/tab-grp` sekmesi açık, When sayfa yüklenir, Then
   "Kayıtlı Gruplar" ve "Baileys Grupları" panelleri masaüstünde yan yana
   (2 kolon grid), mobilde alt alta (1 kolon) gösterilmeli — mevcut
   `loadGroups()`/`loadBaileysGroups()` fonksiyonları DEĞİŞMEDEN aynı
   API'lere (`/api/groups`, Baileys grup endpoint'i) istek atmaya devam
   etmeli.
2. [Critical] Given her iki panelde de grup satırları render edildi, When
   kullanıcı satırlara bakar, Then her satır ikon + grup adı + aksiyon
   butonu (Sil/Ekle) içermeli, YENİ bir `.grp-row` CSS sınıfıyla —
   diğer sekmelerdeki `.bl-item` sınıfı DEĞİŞTİRİLMEMELİ.
3. [Critical] Given arama kutusuna metin girildi, When kullanıcı yazmaya
   devam eder, Then hem Kayıtlı hem Baileys panelindeki satırlar
   client-side (JS ile, backend'e YENİ istek atmadan) filtrelenmeli —
   arama kutusu mevcut kodda YOK, bu görevle eklenen tek yeni istemci
   tarafı özellik.
4. [High] Given backend `/api/whatsapp/groups`'ın 202 durumunda döndürdüğü
   `message` alanı ("Taranmadı", "WhatsApp henüz bağlı değil" vb.), When
   bu durum oluşur, Then aynı mesaj metni kullanılarak (API sözleşmesi
   DEĞİŞMEDEN) ikonlu/görsel bir empty-state kartı gösterilmeli.
5. [High] Given "Yenile" butonlarına (`loadGroups()`/`loadBaileysGroups()`)
   tıklandı, When istek devam ederken, Then buton geçici olarak
   "Yenileniyor..." metnine geçip disabled olmalı, istek bitince eski
   haline dönmeli — fonksiyonların KENDİSİ (hangi endpoint'e ne zaman
   istek attığı) değişmeden.
6. [Medium] Given arama sonucunda hiçbir satır eşleşmiyor, When bu durum
   oluşur, Then "Arama sonucu yok" empty-state'i gösterilmeli (backend'e
   hiç istek atılmadan, salt client-side).
7. [Medium] Given kullanıcı arama kutusuna hızlı/beklenmeyen karakterler
   girer (JS hatası riski), When filtreleme çalışır, Then hata olsa bile
   mevcut liste bozulmadan görünmeye devam etmeli (defensive: try/catch
   ile filtre hatası mevcut listeyi silmemeli).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: API'ler normal veri döner | Mevcut API yanıtları (DEĞİŞMEDEN) | DOM'a iki panel render edilir | Kayıtlı N + Baileys M satır, yan yana | AC-1,2 |
| 2 | Arama eşleşmeyeni | (backend'e istek YOK) | Sadece DOM filtrelenir | "Arama sonucu yok" empty-state | AC-3,6 |
| 3 | Kaynak yok: chat_groups.json boş / Baileys taranmadı | Mevcut API `message` alanı (DEĞİŞMEDEN, örn. 202 + `{"message":"..."}`) | Yok | İkonlu empty-state kartı (aynı metin, yeni görsel) | AC-4 |
| 4 | Dış bağımlılık hatası: API 500/ağ hatası | Mevcut JS hata yakalama davranışı (DEĞİŞMEDEN) | Konsola hata düşer (mevcut) | Mevcut hata gösterimi korunur — bu görev YENİ bir hata UI'ı EKLEMİYOR | — |
| 5 | Arama filtre JS hatası (nadiren) | — | try/catch ile yutulur | Liste bozulmadan görünmeye devam eder | AC-7 |

Kısmi başarı: N/A — bu UI-only görevde render işlemi ya tamamlanır ya JS
hatasıyla durur, ara bir "kısmi" durum söz konusu değil.
Hiçbir şey yapılamadı ama hata da yok: AC-7'de ele alındı — arama filtre
hatası sessizce mevcut listeyi KORUMALI (listeyi boşaltmak "hiçbir şey
yapılamadı" durumunu "boş sonuç" gibi göstereceği için YANLIŞ olurdu).
Boş sonuç ↔ hata ayrımı: "Arama sonucu yok" (client-side, veri var ama
filtre eşleşmiyor) ile "Taranmadı"/"Bağlı değil" (backend'den gelen gerçek
boş durum) GÖRSEL olarak farklı empty-state'lerle ayrılmalı — aynı kutuyu
kullanmak bu ayrımı bozar.

Yetkisiz erişim, Zaman aşımı, Kısmi başarı satırları silindi — bu görev
backend/auth'a dokunmuyor, timeout mekanizması eklemiyor, render ya tam
olur ya JS hatasıyla durur (ara durum yok).

## Test Strategy
Unit: 15% — client-side filtreleme fonksiyonunun (JS, boş/eşleşmeyen/eşleşen girdilerle) mantığı
Integration: 15% — mevcut `loadGroups()`/`loadBaileysGroups()`'ın API sözleşmesinin DEĞİŞMEDİĞİNİN doğrulanması (regresyon)
E2E: 70% — Playwright ile gerçek kullanıcı akışı: sayfa yüklenir → iki panel görünür → arama yazılır/filtrelenir → Ekle/Sil/Yenile tıklanır → empty-state'ler (taranmadı, bağlı değil, arama sonucu yok) doğrulanır

## Benchmark / Başarı Ölçütü
Coverage Target: 50% (çoğu doğrulama E2E/görsel, satır bazlı coverage hedefi düşük tutuluyor)
Performance Target: yok (UI-only görev)
Memory: yok
Görsel/UI kriteri: `verify` adımında `vision-test` skill'i AKTİF çalışmalı
(N/A değil) — kullanıcı zaten v0 tasarımını görsel olarak onayladı, bu
onayın gerçek implementasyonda da karşılandığı görsel olarak doğrulanmalı.
Diğer ölçülebilir kriterler: mevcut `.bl-item`, `--acc`/`--bg`/`--ok`/`--err`
CSS değişkenlerinin ve diğer sekmelerin (Loglar, Kara Liste, Ayarlar)
görsel olarak DEĞİŞMEDİĞİ (regresyon) doğrulanmalı.

## Kapsam Dışı
- Yeni bir backend endpoint'i veya API sözleşmesi değişikliği
- Yeni bir veri alanı (örn. "grup üye sayısı" — v0'ın mock verisinde vardı
  ama gerçek `/api/groups`/Baileys API'si bu veriyi sağlamıyor, EKLENMEYECEK)
- Diğer sekmelerin (Loglar, Kara Liste, Ayarlar) tasarımının değişmesi
- QR kod alanının (`#baileys-qr-section`) veya "Bağlantıyı Kes" butonunun
  DAVRANIŞININ değişmesi (görsel ince ayar dışında — bu ATDD'nin AC'leri
  QR/bağlantı-kesme akışını kapsamıyor, mevcut haliyle korunacak)

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` (INDEX_HTML string sabiti — `#tab-grp` div'i,
  ilgili CSS ve JS fonksiyonları)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımı başlamadan önce `git rev-parse
--show-toplevel` ile kontrol edilecek.

## Rollback Beklentisi
Şema/migration değişikliği yok, düz HTML/CSS/JS string değişikliği. Sorun
çıkarsa `git revert` yeterli.

## Risks
- Tek bir dosyaya (INDEX_HTML string sabiti) gömülü HTML/CSS/JS'in
  büyüklüğü — code-copilot'un doğru bölümü (sadece `#tab-grp` ve ilgili
  fonksiyonlar) izole edip diğer sekmeleri etkilememesi kritik, plan
  adımında tam satır aralıkları netleştirilmeli.
- v0'ın ürettiği tasarımda "grup üye sayısı" gibi gerçek backend'in
  sağlamadığı alanlar vardı (Kapsam Dışı'nda belirtildi) — code-copilot
  bu alanları YOK SAYMALI, uydurma veri göstermemeli.

## Assumptions
- Kullanıcının onayladığı Artifact'taki (https://claude.ai/code/artifact/b0788abc-5c7a-4e71-b042-3df18307c89c)
  tasarım dili (2 panel, arama, empty-state'ler, bağlantı rozeti) bu
  ATDD'nin temel referansı olarak kabul edildi — kullanıcı bunu görsel
  olarak zaten onayladığı için tekrar sorulmadı.
- `.grp-row` gibi yeni CSS sınıf isimleri code-copilot'un kararına
  bırakıldı (plan.md'de netleştirilebilir), tam isimler bağlayıcı değil.

## Unknowns
- Backend'in `/api/whatsapp/groups` 202 yanıtındaki `message` alanının tam
  metin varyasyonları (kaç farklı durum var) `plan` adımında koda bakılarak
  netleştirilmeli.

## Sorular ve Cevaplar (ham kayıt)
1. Arama client-side mi → EVET (Haiku alt-ajanı tarafından yanıtlandı: backend'e dokunmadan en basit çözüm)
2. `.bl-item` mi yeni `.grp-row` mu → yeni `.grp-row`, diğer sekmeler etkilenmesin (Haiku alt-ajanı tarafından yanıtlandı)
3. Empty-state metin mi görsel kart mı → görsel kart, aynı backend mesajı kullanılarak (Haiku alt-ajanı tarafından yanıtlandı)
4. Yenile butonu geri bildirimi → EVET, "Yenileniyor..." + disabled (Haiku alt-ajanı tarafından yanıtlandı)
5. Test oranı → 15/15/70 (Haiku alt-ajanı tarafından yanıtlandı: UI-only görev, E2E ağırlıklı)
6. Benchmark → vision-test + Playwright E2E, coverage %50 (Haiku alt-ajanı tarafından yanıtlandı)
7. Kapsam dışı → yeni endpoint, üye sayısı alanı, diğer sekmeler (Haiku alt-ajanı tarafından yanıtlandı, kullanıcı mesajından da destekleniyor)
8. Rollback → git revert yeterli (Haiku alt-ajanı tarafından yanıtlandı)
9. Kabul kriteri sahibi → görsel onay önemli, vision-test aktif olmalı (Haiku alt-ajanı tarafından yanıtlandı, kullanıcının Artifact'ı zaten görsel onayladığı gerçeğiyle tutarlı)
