---
task_slug: gruplar-tab-iyilestirme-v2
jira_id: null
saga_task_id: 365
priority: medium
coverage_target: 60
performance_target: null
memory_target: null
test_strategy:
  unit: 40
  integration: 30
  e2e: 30
affected_modules:
  - sidecar/bridge.js
  - src/api/admin_panel.py
---

# ATDD — gruplar-tab-iyilestirme-v2

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev. Saga #365 altında takip ediliyor.

## Persona
Sistem operatörü — deploy edilen "Gruplar" sekmesini (gruplar-tab-ui-yenileme,
commit 6b770c3) canlıda kullanırken 3 sorunla karşılaştı.

## Hedef (Neden)
Önceki görev CSS'i projenin sade sistemine uyarlarken v0'ın önerdiği bazı
görsel zenginleştirmeleri (ikon/rozet/boşluk) atlamıştı; 100 kayıtlı grup
tek seferde render edildiği için liste çok uzun; Baileys'ten gelen bazı
gruplar boş `subject` ile geliyor ve isimsiz görünüyor. Bu görev üçünü
birlikte düzeltiyor.

## User Story
As a sistem operatörü
I want Gruplar sekmesinin (1) v0'ın önerdiği görsel detaylara daha yakın
olmasını, (2) uzun listede sayfalanmış gezinmeyi, (3) her grubun bir isimle
görünmesini
So that paneli daha rahat kullanabileyim ve hiçbir grubu gözden kaçırmayayım

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given `sidecar/bridge.js`'in `writeGroupsState()` fonksiyonu
   Baileys'ten gelen bir grubun `subject` alanı boş/undefined, When bu
   grup `data/baileys_groups.json`'a yazılır, Then grup adı "İsimsiz Grup
   (…<id'nin son 6 karakteri>)" formatında bir fallback isimle
   kalıcılaştırılmalı — filtrelenmemeli, veri kaybı yaratılmamalı.
2. [Critical] Given "Kayıtlı Gruplar" panelinde 20'den fazla grup var, When
   panel yüklenir, Then sadece ilk 20 grup gösterilmeli, altında
   sayfa numaraları/ileri-geri navigasyonu olmalı (client-side, backend'e
   yeni istek atılmadan — mevcut `/api/groups` zaten tüm listeyi dönüyor).
3. [High] Given kullanıcı arama kutusuna bir sorgu girer (pagination aktif
   iken), When arama filtrelenmiş sonuç kümesi değişir, Then pagination
   otomatik olarak 1. sayfaya dönmeli ve sayfa sayısı yeni (filtrelenmiş)
   toplam üzerinden yeniden hesaplanmalı.
4. [High] Given Gruplar sekmesindeki panel/satır tasarımı, When kullanıcı
   sayfayı görüntüler, Then v0'ın önerdiği görsel detaylardan (ikon
   kullanımı, rozet stili, satır içi boşluklar) projenin MEVCUT CSS
   sistemine (`--acc`, `--bg` değişkenleri, `.card`/`.b-ok`/`.b-err`
   sınıfları) uyarlanmış hâliyle uygulanmalı — yeni font/renk paleti
   EKLENMEMELİ, diğer sekmelerle tutarlılık korunmalı.
5. [Medium] Given "Baileys Grupları" (henüz eklenmemiş) panelinde de
   isimsiz gruplar olabilir, When bu panel render edilir, Then AYNI
   fallback isim mantığından (AC-1, tek veri kaynağı) otomatik
   yararlanmalı — bu panel için ayrı bir düzeltme YAZILMAYACAK.
6. [Medium] Given "Baileys Grupları" paneli genelde kısa bir liste, When
   bu panel görüntülenir, Then pagination bu panele UYGULANMAYACAK
   (sadece Kayıtlı Gruplar panelinde).

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path: 100 grup, pagination aktif | Mevcut `/api/groups` yanıtı (DEĞİŞMEDEN) | Sadece client-side render bölünüyor | Sayfa başına 20 grup, sayfa 1/5 gibi bir gösterge | AC-2 |
| 2 | Arama + pagination birlikte | (backend'e istek YOK) | Sayfa 1'e sıfırlanır | Filtrelenmiş sonuçlar sayfa 1'den başlar | AC-3 |
| 3 | Kaynak yok: subject boş/undefined | `data/baileys_groups.json`'a fallback isimle yazılır | Kalıcı veri değişikliği (fallback isim) | "İsimsiz Grup (…abc123)" gibi bir isim görünür | AC-1 |
| 4 | Dış bağımlılık hatası: Baileys subject hiç döndürmez | AC-3 ile aynı fallback mantığı devreye girer | Yok, hata fırlatılmaz | Aynı fallback isim | AC-1 |
| 5 | Kısmi başarı: aynı sayfada isimli+isimsiz gruplar karışık | Normal liste | Yok | İkisi de görünür, sıralama bozulmaz | AC-1,2 |
| 6 | Hiçbir şey yapılamadı ama hata yok: isimsiz grup | Fallback isimle GÖSTERİLİR (filtrelenmez) | Yok | Grup listede kalır, kullanıcı yine de "Ekle" diyebilir | AC-1 |

Yetkisiz erişim, Zaman aşımı satırları silindi — bu görev backend/auth'a
dokunmuyor, `/api/groups` zaten senkron ve hızlı, timeout senaryosu kapsam
dışı.

## Test Strategy
Unit: 40% — `writeGroupsState()`'in fallback isim mantığı (subject boş/
undefined/whitespace-only girdilerle)
Integration: 30% — pagination + arama etkileşiminin (sayfa 1'e dönme,
toplam sayfa sayısı yeniden hesaplama) doğru çalıştığının doğrulanması
E2E: 30% — Playwright ile: 20+ grup mock/gerçek veriyle sayfalama arasında
gezinme, arama yapınca sayfa sıfırlanması, isimsiz grubun fallback isimle
görünmesi

## Benchmark / Başarı Ölçütü
Coverage Target: 60%
Performance Target: yok
Memory: yok
Görsel/UI kriteri: `verify` adımında `vision-test` AKTİF olmalı (bu görev
CSS/UI'a dokunuyor).
Diğer ölçülebilir kriterler: sayfa başına tam 20 grup gösterilmesi (fonksiyonel).

## Kapsam Dışı
- Backend'e yeni bir sayfalama endpoint'i/parametresi eklemek
- v0'ın tam görsel dilini (font değişikliği, farklı renk paleti) birebir
  kopyalamak
- Baileys Grupları panelinde ayrı bir pagination eklemek
- Baileys Grupları paneli için ayrı bir isimsiz-grup düzeltmesi yazmak
  (AC-5'te belirtildiği gibi tek veri kaynağından otomatik kapsanıyor)

## Etkilenen Dosyalar/Modüller (bilinen)
- `sidecar/bridge.js` (`writeGroupsState()` fonksiyonu — fallback isim)
- `src/api/admin_panel.py` (`INDEX_HTML` — pagination JS/CSS, görsel
  zenginleştirmeler)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — `plan` adımı başlamadan önce `git rev-parse
--show-toplevel` ile kontrol edilecek.

## Rollback Beklentisi
Şema/migration değişikliği yok, düz kod değişikliği. Sorun çıkarsa `git
revert` yeterli — bridge.js'in fallback ismi sadece görüntüleme/yazma
mantığı, geriye dönük veri bozulması yaratmaz.

## Risks
- `writeGroupsState()`'in fallback isim formatı ("İsimsiz Grup
  (…<id'nin son 6 karakteri>)") kesin ID formatının Baileys grup ID'lerinde
  (`<sayı>@g.us` gibi) nasıl görüneceği `plan` adımında netleştirilmeli —
  ID'nin sonu `@g.us` gibi sabit bir sonek içeriyorsa "son 6 karakter" hep
  aynı görünebilir, gerçek ayırt edici kısmı almak gerekebilir.
- Client-side pagination + arama'nın birlikte doğru çalışması, mevcut
  `filterGroups()` fonksiyonuyla (bir önceki görevde eklenmişti)
  entegrasyonu gerektiriyor — `plan` adımında mevcut kodun tam yapısı
  incelenmeli.

## Assumptions
- Sayfa başına 20 grup gösterimi kullanıcı tarafından net onaylanmadı,
  Sonnet 5 alt-ajanının önerisiyle kabul edildi — makul bir varsayılan.
- "İsimsiz Grup (…son6karakter)" formatı kesinleşmiş değil, plan adımında
  Baileys ID formatına göre ayarlanabilir.

## Unknowns
- Baileys grup ID'lerinin gerçek formatı (örn. `120363024125432@g.us`) —
  fallback isim formatının bu ID'yi nasıl kısaltacağı `plan` adımında
  netleştirilmeli.

## Sorular ve Cevaplar (ham kayıt)
1. CSS hedefi → mevcut sistem korunsun, sadece görsel detaylar eklensin (Sonnet 5 alt-ajanı tarafından yanıtlandı)
2. Pagination yaklaşımı → client-side, sayfa başına 20 (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Arama + pagination → arama sayfa 1'e döner (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. İsimsiz grup düzeltme yeri → bridge.js writeGroupsState() (kaynağında) (Sonnet 5 alt-ajanı tarafından yanıtlandı)
5. İsimsiz grup filtrelenir mi → HAYIR, fallback isimle gösterilir (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Test stratejisi → 40/30/30 (Sonnet 5 alt-ajanı tarafından yanıtlandı)
7. Benchmark → sayısal hedef yok, vision-test aktif (Sonnet 5 alt-ajanı tarafından yanıtlandı)
8. Kapsam dışı → yeni backend endpoint, tam v0 kopyası, Baileys panelinde ayrı pagination/fix (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Rollback → git revert yeterli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
