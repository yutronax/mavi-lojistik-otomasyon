---
task_slug: blacklist-pagination
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

# ATDD — blacklist-pagination

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev.

## Saga Kaynağı
Saga'ya bağlı değil — bu ortamda `project_id` bilinmiyor/yapılandırılmamış (saga_task_id: null).

## Persona
Mavi Lojistik'in web admin panelini kullanan iç ekip/operatör (harici müşteri yok, `@require_auth` ile korunan dahili operasyon aracı). (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## Hedef (Neden)
Kara Liste sekmesi şu an 111+ kaydı tek DOM'a basıyor; bu sayfayı gereksiz uzatıp scroll'u yoruyor ve zaten pagination'a sahip "Gruplar" sekmesiyle tutarsız bir UX yaratıyor. Sorun performans değil, gezinme/okunabilirlik — pagination kayıtları 20'şerlik sayfalara bölerek çözüyor. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## User Story
As a Mavi Lojistik admin panel operatörü
I want Kara Liste sekmesindeki numaraların Gruplar sekmesindeki gibi sayfalara bölünmüş görünmesini
So that uzun listede kolayca gezinebileyim, sayfa aşırı uzamasın

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given Kara Liste sekmesinde 20'den fazla kayıt (ör. 111), When sekme açılırsa, Then `#bl-list` içinde her seferinde en fazla 20 satır `display:''` (görünür) olur, kalanı `display:none`, ve `#bl-pagination` bölümünde ⌈toplam/20⌉ sayfa numarası + `‹`/`›` butonları görünür.
2. [Critical] Given pagination görünürken, When kullanıcı bir sayfa numarasına tıklarsa, Then o sayfanın aralığındaki satırlar görünür olur, diğerleri gizlenir, aktif sayfa numarası vurgulanır — ek bir ağ isteği yapılmadan (client-side, senkron).
3. [High] Given toplam kayıt sayısı 20'ye eşit veya daha az, When sekme açılırsa veya arama sonucu bu sayıya düşerse, Then `#bl-pagination` bölümü tamamen gizlenir (Gruplar sekmesiyle birebir tutarlı davranış).
4. [High] Given kullanıcı arama kutusuna (`#bl-q`) bir şey yazdı ve sonuç kümesi değişti, When `loadBl()` yeniden çalışırsa, Then sayfa her zaman 1'e döner ve pagination yeni (daha kısa/uzun) sonuç kümesine göre yeniden hesaplanır.
5. [Medium] Given kullanıcı herhangi bir sayfada bir kayıt sildi (`blDel`), When silme işlemi tamamlanırsa, Then `loadBl()` listeyi yeniden yükler ve sayfa **her zaman 1'e döner** — kullanıcı asla boş bir sayfada bırakılmaz. **(Karar değişikliği, 2026-09-06):** İlk taslakta "bir önceki geçerli sayfaya dönme" planlanmıştı; red-team incelemesi bunun gerçek implementasyonla (her zaman sayfa 1'e reset) uyuşmadığını tespit etti, kullanıcıya soruldu ve kullanıcı basit "her zaman sayfa 1" davranışını onayladı (ek clamp mantığına gerek yok).
6. [Medium] Given pagination JS'inde beklenmeyen bir hata oluşursa, When `renderBlPagination` exception fırlatırsa, Then mevcut `loadBl()`'ün temel liste render akışı (`#bl-list` doldurma) bundan etkilenmez — pagination ayrı, izole bir katman olarak eklenir.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (111 kayıt, sayfa 1) | `renderBlPagination(1)` DOM'u günceller, dönüş değeri yok (void) | `#bl-list`'teki ilk 20 `.bl-item` görünür, kalanı gizli | 6 sayfa numarası + ‹/› butonları, sayfa "1" vurgulu | AC-1 |
| 2 | Kaynak yok (blacklist boş) | `renderBlPagination` çağrılır, `visibleRows.length === 0` | `#bl-pagination` gizli kalır | "Toplam 0 numara" mesajı, boş liste, pagination hiç görünmez | AC-3 |
| 3 | Kısmi başarı (arama+pagination birlikte, eski sayfa numarası yeni sonuç kümesiyle uyuşmuyor) | `loadBl()` her çağrıldığında sayfa zorla 1'e resetlenir | `blSearchMatches` güncellenir, `renderBlPagination(1)` çağrılır | Arama sonrası her zaman sayfa 1 gösterilir, asla boş/tutarsız sayfa görünmez | AC-4 |
| 4 | Hiçbir şey yapılamadı ama hata yok (son sayfadaki tek kayıt silindi) | `loadBl()` listeyi yeniden çeker, `renderBlPagination(1)` çağrılır | Görüntülenen sayfa her zaman 1'e döner | Kullanıcı boş bir sayfada kalmaz, sayfa 1'i görür (kullanıcı onaylı sadeleştirme) | AC-5 |

Satırlar "Girdi geçersiz/eksik", "Yetkisiz erişim", "Dış bağımlılık hatası", "Zaman aşımı" silindi: bu tamamen client-side, girdi almayan bir DOM-render özelliği — `renderBlPagination` hiçbir parametre/kullanıcı girdisi doğrulamıyor, backend `@require_auth` bu görevde değişmiyor, ağ çağrısı yapmıyor (senkron DOM manipülasyonu), bu yüzden bu dört satırın hiçbiri bu özelliğe uygulanmıyor. (Sonnet 5 alt-ajanı gerekçesi)

Kısmi başarı: Arama+pagination birlikte kullanılırken oluşabilecek tutarsızlık, her `loadBl()` çağrısında sayfayı zorla 1'e resetleyerek engellenir (bkz. satır 3).
Hiçbir şey yapılamadı ama hata yok: Son sayfa boşalırsa sessizce boş kalmak YASAK — otomatik bir önceki geçerli sayfaya dönülür (bkz. satır 4).
Boş sonuç ↔ hata ayrımı: Blacklist boş olması ("Toplam 0 numara" + pagination gizli) ile bir JS hatası (pagination'ın render edilememesi) arada `#bl-list`'in temel render akışını bozmaması ile ayrılır (AC-6) — ikisi de aynı görsel sonucu üretmez.

## Test Strategy
Unit: 10% — mevcut `/api/blacklist` GET backend pytest testleri (varsa) bu değişiklikten etkilenmemeli, regresyon olarak çalıştırılır.
Integration: 0% — bu görev backend route'una dokunmuyor, entegrasyon testi gerektirmiyor.
E2E: 90% — tarayıcıda manuel/e2e doğrulama: 20+ kayıtla sayfa geçişi, arama+pagination birlikte kullanımı, silme sonrası sayfa clamp davranışı, ≤20 kayıtla pagination'ın gizli kalması. (Proje JS birim testi altyapısına sahip değil, bunu bu görevde kurmak kapsam dışı — Sonnet 5 alt-ajanı gerekçesi)

## Benchmark / Başarı Ölçütü
Coverage Target: 60% (backend regresyon testleri için; JS kod coverage'ı bu projede ölçülmüyor)
Performance Target: Sayfa geçişi ek ağ isteği yapmadan, DOM manipülasyonu ile anlık/senkron olmalı.
Memory: yok
Görsel/UI kriteri: 111 kayıtla herhangi bir sayfada DOM'da en fazla 20 `.bl-item` görünür (`display:''`) olmalı; pagination görünümü Gruplar sekmesiyle (buton stili, `‹`/`›` okları, aktif sayfa vurgusu) birebir tutarlı olmalı. Bu kriter `verify` adımında `vision-test` ile kontrol edilecek.
Diğer ölçülebilir kriterler: Arama sonrası sayfa her zaman 1'den başlamalı.

## Kapsam Dışı
- Server-side pagination'a geçiş yok.
- `/api/blacklist`'in mevcut `items[:200]` limitinin kaldırılması/artırılması yok.
- Sayfa boyutunun (20) kullanıcı tarafından değiştirilebilir hale getirilmesi yok.
- Gruplar sekmesindeki mevcut `renderGrpPagination`/`ITEMS_PER_PAGE`/`currentPage` koduna dokunma yok — sadece desen örnek alınıp kara liste için ayrı, izole bir kopyası (`renderBlPagination`, ayrı `blSearchMatches`/`blCurrentPage` durumu) yazılacak.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/api/admin_panel.py` (gömülü HTML/CSS/JS bölümü — `#bl-list`/`#bl-pagination` render mantığı, `loadBl()` fonksiyonu, yeni `renderBlPagination()` fonksiyonu)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu worktree'nin git kökü proje klasörüyle aynı görünüyor (`C:\...\maviLojistik\.claude\worktrees\festive-pare-2fb538`), ancak daha geniş bir ev dizini/devasa git geçmişi olup olmadığı bu görev kapsamında ayrıca doğrulanmadı. Sonraki adımlar aramalarını `src/api/admin_panel.py` ile sınırlı tutmalı.

## Rollback Beklentisi
Pagination JS'inde bir hata oluşursa mevcut `#bl-list` render akışı (`loadBl()`'ün temel listeleme mantığı) bundan etkilenmemeli — pagination ayrı, izole bir katman/fonksiyon olarak eklenmeli, mevcut listeleme mantığının içine invaziv şekilde gömülmemeli.

## Risks
- Gruplar sekmesindeki `currentPage`/`grpSearchMatches` global JS değişkenleriyle isim çakışması riski — kara liste için ayrı isimlendirilmiş (`blCurrentPage`, `blSearchMatches`) durum değişkenleri kullanılmalı, aksi halde iki sekme birbirinin pagination durumunu bozabilir.
- Bu tamamen manuel/e2e doğrulamaya dayanan bir görev; otomatik regresyon koruması zayıf, ileride bir refactor bu davranışı fark edilmeden bozabilir.

## Assumptions
- Kullanıcı onaylamadıysa: sayfa boyutunun Gruplar sekmesiyle aynı (20) olması varsayıldı — Sonnet 5 alt-ajanı önerisi, kullanıcı farklı bir sayı istemedi.
- Silme sonrası "bir önceki sayfaya dönme" davranışı varsayımdır (kod tabanında bu senaryo için mevcut bir emsal yok) — kullanıcı onayı gerekiyor.

## Unknowns
- Backend `/api/blacklist` GET için mevcut bir pytest testi olup olmadığı bu görevde doğrulanmadı — `plan` adımında kontrol edilmeli.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü / persona → İç ekip/operatör, dahili admin paneli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
2. Ana hedef / neden → Uzun liste gezinme/okunabilirlik sorunu, Gruplar sekmesiyle tutarlılık (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Happy path → 111 kayıt, 6 sayfa, sayfa 1'de 20 satır (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. Edge case (arama+pagination) → her loadBl() sonrası sayfa 1'e reset (Sonnet 5 alt-ajanı tarafından yanıtlandı)
5. Edge case (≤20 kayıt) → pagination tamamen gizlenir (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Edge case (silme sonrası boş sayfa) → Math.min(currentPage, totalPages) ile clamp (Sonnet 5 alt-ajanı tarafından yanıtlandı, varsayım olarak işaretli)
7. Davranış sözleşmesi tablosu → yukarıdaki tabloya işlendi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
8. Başarı ölçütü → en fazla 20 görünür satır, senkron sayfa geçişi, arama sonrası sayfa 1 (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Kapsam dışı → server-side pagination, limit değişikliği, sayfa boyutu ayarı, Gruplar koduna dokunma yok (Sonnet 5 alt-ajanı tarafından yanıtlandı)
10. Bağımlılıklar → sadece admin_panel.py (Sonnet 5 alt-ajanı tarafından yanıtlandı)
11. Test stratejisi → %10 unit / %0 integration / %90 e2e-manuel (Sonnet 5 alt-ajanı tarafından yanıtlandı)
12. Rollback beklentisi → pagination hatası ana liste render'ını etkilememeli (Sonnet 5 alt-ajanı tarafından yanıtlandı)
