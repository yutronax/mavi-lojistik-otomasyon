---
task_slug: baileys-groups-pagination
jira_id: null
saga_task_id: null
priority: medium
coverage_target: 60
performance_target: null
memory_target: null
test_strategy:
  unit: 10
  integration: 0
  e2e: 90
affected_modules:
  - src/api/admin_panel.py
---

# ATDD — baileys-groups-pagination

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev.

## Saga Kaynağı
Saga'ya bağlı değil — bu ortamda `project_id` bilinmiyor/yapılandırılmamış.

## Persona
Mavi Lojistik'in web admin panelini kullanan iç ekip/operatör — "Kayıtlı Gruplar" ve "Kara Liste"de zaten pagination kullanan aynı kullanıcı. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## Hedef (Neden)
Kayıtlı Gruplar/Kara Liste'den farklı olarak burada asıl motivasyon **tutarlılık değil performans/kullanılabilirlik**: WhatsApp'tan (Baileys köprüsü) çekilen grup sayısı büyük olabiliyor, tüm satırların tek sayfada DOM'a basılması arayüzü yavaşlatıyor/uzatıyor. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## User Story
As a Mavi Lojistik admin panel operatörü
I want Baileys'ten çekilen WhatsApp gruplarının da Kayıtlı Gruplar/Kara Liste gibi sayfalara bölünmüş görünmesini
So that büyük grup listelerinde arayüz yavaşlamasın, gezinme kolaylaşsın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given "Baileys Grupları" panelinde 20'den fazla grup (ör. 45), When panel açılıp `loadBaileysGroups()` çalışırsa, Then `#baileys-available-groups-list` içinde en fazla 20 `.grp-row` görünür olur, kalanı gizlenir, ve yeni bir pagination bölümünde ⌈toplam/20⌉ sayfa numarası + `‹`/`›` butonları görünür.
2. [Critical] Given pagination görünürken, When kullanıcı bir sayfa numarasına tıklarsa, Then `renderBaileysGrpPagination(page)` o sayfanın aralığındaki satırları gösterir, diğerlerini gizler — izole `baileysCurrentPage` state'iyle, Gruplar'ın `currentPage`'ini veya Kara Liste'nin `blCurrentPage`'ini ETKİLEMEDEN.
3. [High] Given toplam Baileys grup sayısı 20'ye eşit veya daha az, When liste yüklenir veya arama sonucu bu sayıya düşerse, Then pagination bölümü tamamen gizlenir (diğer iki pagination'la tutarlı).
4. [High] Given "Kayıtlı Gruplar" ve "Baileys Grupları" AYNI arama kutusunu (`#grp-search`, `filterGroups()`) paylaşıyor, When kullanıcı arama yaparsa, Then HEM `currentPage` HEM `baileysCurrentPage` sıfırlanır, her iki listenin pagination'ı da kendi filtrelenmiş sonuç kümesine göre yeniden hesaplanır.
5. [Medium] Given kullanıcı "⟳" (yenile) butonuna tıklayıp `loadBaileysGroups()`'u tekrar çalıştırdı, When yeni grup listesi gelirse, Then `baileysCurrentPage` 1'e döner ve pagination yeniden hesaplanır (Kayıtlı Gruplar/Kara Liste'nin `loadGroups()`/`loadBl()` deseniyle tutarlı).
6. [Medium] Given `renderBaileysGrpPagination` içinde beklenmeyen bir hata oluşursa, When exception fırlatılırsa, Then `loadBaileysGroups()`'un temel liste render akışı (`#baileys-available-groups-list` doldurma) bundan etkilenmez.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (45 grup, sayfa 1) | `renderBaileysGrpPagination(1)` DOM günceller | İlk 20 `.grp-row` görünür | 3 sayfa numarası + ‹/› | AC-1 |
| 2 | Kaynak yok (Baileys'ten hiç grup gelmedi) | `visibleRows.length === 0` | Pagination gizli kalır | Mevcut boş-liste mesajı (bu görevde değişmiyor) | AC-3 |
| 3 | Dış bağımlılık hatası (Baileys köprüsü bağlı değil/hata döner) | Pagination katmanı bunu ELE ALMAZ | `loadBaileysGroups()`'un mevcut hata gösterme mantığı değişmeden kalır | Mevcut hata mesajı (bu görevin kapsamı dışı) | — |
| 4 | Hiçbir şey yapılamadı ama hata yok (ortak arama sonrası eski sayfa numarası geçersiz kalırsa) | `filterGroups()` her iki `*CurrentPage`'i de sıfırlar | Her iki liste de sayfa 1'e döner | Tutarlı, boş olmayan bir sayfa | AC-4 |

Satırlar "Girdi geçersiz/eksik", "Yetkisiz erişim", "Zaman aşımı", "Kısmi başarı" silindi: pagination katmanı kullanıcı girdisi almıyor (sadece sayfa tıklaması), admin panel tek-oturumlu (ayrı yetki katmanı bu görevde değişmiyor), client-side senkron DOM manipülasyonu ağ çağrısı/zaman aşımı içermiyor, ve backend'den kısmi veri gelmesi `loadBaileysGroups()`'un kendi sorumluluğu (bu görev sadece render edilen satırlar üzerinde çalışıyor). (Sonnet 5 alt-ajanı gerekçesi)

Kısmi başarı: Uygulanmıyor (bkz. yukarı) — pagination her zaman DOM'daki mevcut tam satır kümesi üzerinde çalışır, backend'in kısmi/eksik veri döndürmesi ayrı bir konudur.
Hiçbir şey yapılamadı ama hata yok: Ortak arama kutusu tetiklendiğinde iki pagination state'i de senkron sıfırlanarak, kullanıcının "boş" veya tutarsız bir sayfada kalması engellenir (AC-4).
Boş sonuç ↔ hata ayrımı: "Baileys'ten hiç grup gelmedi" (pagination gizli + mevcut boş-liste mesajı) ile "Baileys köprüsü hata döndü" (mevcut hata gösterme mantığı, bu görevde değişmiyor) birbirinden ayrı kalmaya devam ediyor — pagination katmanı bu ayrımı bozmuyor, sadece dokunmuyor.

## Test Strategy
Unit: 10% — yapısal string/regex testler (`tests/test_baileys_grp_pagination.py`), `test_gruplar_tab_ui.py`/`test_blacklist_pagination.py` ile aynı desen.
Integration: 0% — backend route değişmiyor.
E2E: 90% — tarayıcıda manuel/e2e doğrulama: 20+ grupla sayfa geçişi, ortak arama+iki pagination'ın birlikte reset olması, yenile butonu sonrası sayfa 1'e dönme, ≤20 grupta gizlenme. (Sonnet 5 alt-ajanı gerekçesi: gerçek JS runtime test altyapısı yok)

## Benchmark / Başarı Ölçütü
Coverage Target: 60%
Performance Target: Sayfa geçişi ek ağ isteği yapmadan, DOM manipülasyonu ile anlık/senkron olmalı.
Memory: yok
Görsel/UI kriteri: 45 grupla herhangi bir sayfada `#baileys-available-groups-list` içinde en fazla 20 `.grp-row` görünür olmalı; pagination görünümü diğer iki pagination'la (buton stili, ok karakterleri, aktif sayfa vurgusu) birebir tutarlı olmalı. `verify` adımında `vision-test` ile kontrol edilecek.
Diğer ölçülebilir kriterler: Ortak arama sonrası her iki liste de sayfa 1'den başlamalı; yenile sonrası Baileys listesi sayfa 1'den başlamalı.

## Kapsam Dışı
- Baileys köprüsü API'sinin kendisi (bağlantı, hata yönetimi, timeout) değişmeyecek.
- `filterGroups()`'un hangi satırın eşleştiğini belirleyen filtreleme mantığı değişmeyecek — sadece filtrelenmiş/görünür satırlar üzerinde pagination katmanı eklenecek.
- Sayfa boyutunun (20) kullanıcı tarafından değiştirilebilir hale getirilmesi yok.
- Kayıtlı Gruplar'ın (`renderGrpPagination`/`currentPage`) veya Kara Liste'nin (`renderBlPagination`/`blCurrentPage`) mevcut koduna dokunma yok — sadece üçüncü, izole bir kopya (`renderBaileysGrpPagination`, `baileysCurrentPage`) eklenecek.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` (gömülü HTML/CSS/JS — `#baileys-available-groups-list` render mantığı, `loadBaileysGroups()`, `filterGroups()`, yeni `renderBaileysGrpPagination()`)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu worktree'nin git kökü proje klasörüyle aynı görünüyor, ancak daha geniş bir dizin/devasa git geçmişi olup olmadığı ayrıca doğrulanmadı. Aramalar `src/api/admin_panel.py` ile sınırlı tutulmalı.

## Rollback Beklentisi
`renderBaileysGrpPagination`'daki bir hata `loadBaileysGroups()`'un temel `#baileys-available-groups-list` render akışını etkilememeli — pagination arızalanırsa en kötü ihtimalle tüm satırlar görünür kalır (fail-safe), ama liste kendisi bozulmaz. (Sonnet 5 alt-ajanı gerekçesi)

## Risks
- `filterGroups()` HER İKİ listeyi (Kayıtlı Gruplar + Baileys Grupları) aynı anda filtrelediği için, bu fonksiyona pagination-reset mantığı eklerken sadece bir listeyi resetleyip diğerini unutma riski var — her iki `*CurrentPage`'in de senkron sıfırlanması test edilmeli (AC-4).
- Üç farklı pagination implementasyonunun (Gruplar/Kara Liste/Baileys) aynı dosyada birbirine çok benzer ama izole kod olarak durması, gelecekte bir bakım yükü oluşturabilir (kod tekrarı) — ancak bu üç görevin bilinçli bir tasarım kararı (CAVEMAN: erken soyutlama yerine, gerçek bir üçüncü tekrar ortaya çıkana kadar kopyalama tercih edildi).

## Assumptions
- Baileys grupları için de sayfa boyutunun (20) diğer ikisiyle aynı olması varsayıldı — kullanıcı farklı bir sayı istemedi.
- `loadBaileysGroups()`'un mevcut boş-liste/hata gösterme mantığının bu görevde değişmeyeceği varsayıldı.

## Unknowns
- `filterGroups()`'un tam mevcut kodu (satır ~1674-1704 civarı, önceki görevlerden biliniyor) `plan` adımında tekrar okunup, iki `*CurrentPage` sıfırlamasının nereye ekleneceği netleştirilmeli.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü / persona → Aynı admin panel operatörü (Sonnet 5 alt-ajanı tarafından yanıtlandı)
2. Ana hedef / neden → Performans/kullanılabilirlik (büyük grup listesi), tutarlılık ikincil (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Happy path → 45 grup, 3 sayfa, sayfa 1'de 20 satır (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. Edge case (ortak arama kutusu) → her iki *CurrentPage de sıfırlanır (Sonnet 5 alt-ajanı tarafından yanıtlandı)
5. Edge case (yenile butonu) → baileysCurrentPage 1'e döner (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Edge case (≤20 grup) → pagination gizlenir (Sonnet 5 alt-ajanı tarafından yanıtlandı)
7. Davranış sözleşmesi tablosu → yukarıdaki tabloya işlendi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
8. Başarı ölçütü → en fazla 20 görünür satır, senkron sayfa geçişi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Kapsam dışı → Baileys API'si, filterGroups mantığı, sayfa boyutu ayarı, diğer iki pagination koduna dokunma yok (Sonnet 5 alt-ajanı tarafından yanıtlandı)
10. Bağımlılıklar → sadece admin_panel.py (Sonnet 5 alt-ajanı tarafından yanıtlandı)
11. Test stratejisi → %10 unit / %0 integration / %90 e2e-manuel (Sonnet 5 alt-ajanı tarafından yanıtlandı)
12. Rollback beklentisi → pagination hatası ana liste render'ını etkilememeli, fail-safe (tüm satırlar görünür kalır) (Sonnet 5 alt-ajanı tarafından yanıtlandı)
