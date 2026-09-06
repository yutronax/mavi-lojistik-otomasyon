---
task_slug: blacklist-normalize-fix
jira_id: null
saga_task_id: null
priority: high
coverage_target: 85
performance_target: null
memory_target: null
test_strategy:
  unit: 80
  integration: 20
  e2e: 0
affected_modules:
  - src/gui/components/blacklist_tab.py
  - src/services/data_service.py
  - src/utils/phone_utils.py
---

# ATDD — blacklist-normalize-fix

## Jira Kaynağı
Jira'ya bağlı değil — yerel görev (kod incelemesi sırasında bulunan bug).

## Saga Kaynağı
Saga'ya bağlı değil — bu ortamda `project_id` bilinmiyor/yapılandırılmamış (saga_task_id: null). Task takibi bu atdd.md üzerinden yapılacak.

## Persona
Mavi Lojistik operasyon/ofis personeli — masaüstü Flet uygulamasından şüpheli/istenmeyen gönderici numaralarını kara listeye elle ekleyen kişi. (Sonnet 5 alt-ajanı tarafından yanıtlandı: GUI'nin bilinen tek kullanıcı tipi bu.)

## Hedef (Neden)
`blacklist_tab.py`'den eklenen numaralar normalize edilmediği ve "reason" girildiğinde dict formatına döndüğü için `save_blacklist()` içindeki `set(blacklist)` çağrısı unhashable type hatasıyla sessizce başarısız oluyor (kullanıcıya yine de "eklendi" gösteriliyor), ve `is_phone_in_list()` normalize edilmemiş/dict kayıtları hiç eşleştiremiyor — yani blacklist filtresi bu yoldan eklenen numaralar için fiilen çalışmıyor. Düzeltme, GUI'den eklenen numaraların kalıcı olarak kaydedilmesini VE filtrelemenin gerçekten çalışmasını sağlıyor. (Sonnet 5 alt-ajanı tarafından yanıtlandı)

## User Story
As a Mavi Lojistik operasyon personeli
I want kara listeye masaüstü uygulamasından eklediğim bir numaranın doğru kaydedilmesini ve gerçekten filtrelenmesini
So that istenmeyen göndericilerden gelen mesajlar güvenilir şekilde engellensin

## Acceptance Criteria (Given-When-Then, önceliklendirilmiş)
1. [Critical] Given GUI'de boş bir kara liste, When kullanıcı "0532 123 45 67" numarasını (reason olsun/olmasın) eklerse, Then `blacklist.json`'a `"05321234567"` düz normalize string olarak yazılır ve `save_blacklist()` hiçbir exception fırlatmaz.
2. [Critical] Given reason="spam" ile bir numara eklenmişse, When aynı numaradan bir mesaj gelirse, Then `is_phone_in_list()` bu numarayı normalize ederek eşleştirir ve `True` döner (reason bilgisi ayrı bir map'te saklanır, ana filtreleme mantığını bozmaz).
3. [High] Given VPS'teki mevcut 111 düz-string kayıt, When düzeltilmiş `save_blacklist()`/`is_phone_in_list()` bu listeye karşı çalıştırılırsa, Then hiçbir mevcut kayıt bozulmaz/kaybolmaz ve hepsi eskisi gibi eşleşmeye devam eder (geriye dönük uyumluluk).
4. [High] Given listede zaten `"05321234567"` varken, When kullanıcı aynı numarayı `"0532 123 45 67"` (boşluklu) formatında tekrar eklemeye çalışırsa, Then normalize sonrası duplicate tespit edilir, tekrar eklenmez ve kullanıcıya "zaten kara listede" bilgisi gösterilir.
5. [Medium] Given boş veya geçersiz uzunlukta (7 haneden kısa / 15 haneden uzun) bir numara girilirse, When ekleme denenirse, Then kayıt yapılmaz ve kullanıcıya "geçersiz numara" hatası gösterilir.
6. [Medium] Given karışık formatta (bazı düz string, bazı dict) bir `blacklist.json`, When `save_blacklist()` çağrılırsa, Then tüm elemanlar coercion ile düz normalize string'e çevrilip kaydedilir, reason'lar varsa ayrı bir `blacklist_reasons.json`'a taşınır.

## Davranış Sözleşmesi (hangi durumda ne döner)
| # | Durum | Dönen değer / durum kodu | Yan etki | Kullanıcı ne görür | AC |
|---|---|---|---|---|---|
| 1 | Happy path (geçerli TR numarası, reason ile/olmadan) | `save_blacklist()` → `True` | `blacklist.json`'a normalize edilmiş düz string eklenir; reason varsa `blacklist_reasons.json`'a `{numara: reason}` eklenir | "'<numara>' kara listeye eklendi" | AC-1, AC-2 |
| 2 | Girdi geçersiz/eksik (boş, <7 veya >15 hane) | Ekleme fonksiyonu `False`/hata döner, `save_blacklist()` hiç çağrılmaz | Yok | "Geçersiz numara" hatası, alan altı uyarı | AC-5 |
| 3 | Kaynak yok (silinecek numara listede yok) | `_delete_blacklist` no-op, hata fırlatmaz | Yok | "Listede yok" bilgisi | — (mevcut davranış korunur) |
| 4 | Yetkisiz erişim | N/A | N/A | N/A | — |
| 5 | Dış bağımlılık hatası (MongoDB sync başarısız) | Yerel kayıt `True` döner, Mongo hatası ayrıca loglanır | Yerel dosya güncellenir, Mongo senkron değildir | Kullanıcı "eklendi" görür (yerel kayıt esastır), hata kullanıcıyı bloklamaz | — (mevcut davranış korunur, bu görevin kapsamı dışı) |
| 6 | Zaman aşımı | N/A | N/A | N/A | — |
| 7 | Kısmi başarı (toplu ekleme) | N/A — bu görevde toplu ekleme akışı yok | — | — | — |
| 8 | Hiçbir şey yapılamadı ama hata da yok (zaten listede olan numara tekrar eklenmeye çalışılırsa) | Ekleme fonksiyonu `False` + "zaten listede" mesajı döner, `save_blacklist()` çağrılmaz | Yok | "Zaten kara listede" bilgisi (sessiz swallow YASAK) | AC-4 |

Satır 4 (Yetkisiz erişim) ve 6 (Zaman aşımı) silinmedi, N/A olarak işaretlendi: bu yerel/tek-kullanıcılı masaüstü uygulamasında kimlik doğrulama katmanı yok, ve dosya I/O senkron+yerel olduğu için ağ zaman aşımı riski bu görevin kapsamında oluşmuyor. Satır 7 (kısmi başarı) da N/A: GUI'de toplu/bulk ekleme akışı mevcut değil, bu görev onu eklemiyor.

Kısmi başarı: Uygulanmıyor (bkz. satır 7 notu) — tekli ekleme akışı dışında bir senaryo bu görevin kapsamında yok.
Hiçbir şey yapılamadı ama hata da yok: Zaten-listede-var durumu kullanıcıya açıkça "zaten kara listede" olarak gösterilir, sessiz başarı mesajı verilmez (bkz. satır 8).
Boş sonuç ↔ hata ayrımı: "Zaten listede" (AC-4, satır 8) ile "geçersiz numara" (AC-5, satır 2) kullanıcıya farklı, ayrı mesajlarla gösterilir — aynı genel "hata" mesajına düşürülmez.

## Test Strategy
Unit: 80% — `normalize_phone`/`get_phone_variants` ile coercion, `save_blacklist`'in karışık (string+dict) girdiyle patlamadan çalışması, dedup mantığı, `is_phone_in_list`'in eski düz-string ve yeni coerced formatla doğru eşleşmesi.
Integration: 20% — `blacklist_tab.py`'nin `_add_blacklist`/`_delete_blacklist` fonksiyonlarından `data_service.save_blacklist`'e uçtan uca dosya yazma/okuma akışı (gerçek geçici dosya ile).
E2E: 0% — Flet UI otomasyonu bu boyuttaki bug fix için orantısız maliyetli (Sonnet 5 alt-ajanı gerekçesi).

## Benchmark / Başarı Ölçütü
Coverage Target: 85%
Performance Target: yok
Memory: yok
Görsel/UI kriteri: yok (UI değişikliği yalnızca hata/bilgi mesajları metni düzeyinde, layout değişmiyor).
Diğer ölçülebilir kriterler: `save_blacklist()` hiçbir girdi kombinasyonunda (düz string/dict/karışık) exception fırlatmamalı; yeni eklenen her kayıt %100 `normalize_phone()` çıktısı formatında olmalı; VPS'teki mevcut 111 kayıt için `is_phone_in_list()` sonucu değişmemeli (regresyon testi).

## Kapsam Dışı
- `src/api/admin_panel.py`'nin kendi kodu değiştirilmeyecek (sadece normalize mantığı referans alınıyor).
- MongoDB senkronizasyon mantığının kendisi (mevcut best-effort davranış korunur).
- GUI'de toplu/bulk numara ekleme akışı.
- `blacklist_tab.py`'nin genel UI/layout yeniden tasarımı — sadece `_add_blacklist`/`_delete_blacklist` ve ilgili doğrulama/mesaj mantığına dokunulacak.

## Etkilenen Dosyalar/Modüller (bilinen)
- `src/gui/components/blacklist_tab.py` (`_add_blacklist`, `_delete_blacklist`)
- `src/services/data_service.py` (`save_blacklist`, muhtemelen yeni `load_blacklist_reasons`/`save_blacklist_reasons` yardımcı fonksiyonları)
- `src/utils/phone_utils.py` (`is_phone_in_list`)
- Yeni: `data/blacklist_reasons.json` (reason bilgisi için, opsiyonel)
- `tests/` altında yeni test dosyası (ör. `test_blacklist_normalize.py`)

## Proje Ortamı Kısıtı (arama/grep kapsamı)
Doğrulanmadı — bu worktree'nin git kökü proje klasörüyle aynı görünüyor (`C:\...\maviLojistik\.claude\worktrees\festive-pare-2fb538`), ancak daha geniş bir ev dizini/devasa git geçmişi olup olmadığı bu görev kapsamında ayrıca doğrulanmadı. Sonraki adımlar (plan/code-copilot/test-copilot/red-team) aramalarını `src/`, `tests/`, `data/blacklist*.json` ile sınırlı tutmalı.

## Rollback Beklentisi
`save_blacklist()` ve `is_phone_in_list()` her zaman eski düz-string formatını da okuyabilmeli — bu geçici bir geçiş değil, kalıcı bir geriye-dönük-uyumluluk gereksinimi. Düzeltme sonrası bir sorun çıkarsa VPS'teki `blacklist.json` mevcut 111 kayıtla (hiç dokunulmadan) çalışmaya devam etmeli; `blacklist_reasons.json` dosyası silinse veya hiç var olmasa bile ana blacklist filtreleme işlevi etkilenmemeli.

## Risks
- VPS'teki canlı `blacklist.json` üzerinde yanlış bir coercion/migration adımı veri kaybına yol açabilir — bu yüzden değişiklik önce yerel/test verisiyle doğrulanmalı, canlı dosyaya elle dokunulmamalı (deploy pipeline üzerinden gitmeli).
- `blacklist_reasons.json` gibi yeni bir dosya eklemek, mevcut yedekleme/backup akışlarına (`data/backups/`) dahil edilmeyi unutabilir.

## Assumptions
- Reason bilgisinin ayrı bir dosyada saklanması (dict yerine) kabul edilebilir bir tasarım kararı olarak varsayıldı — kullanıcı onaylamadıysa bu varsayımdır. (Sonnet 5 alt-ajanı önerisi)
- MongoDB senkron hatası davranışının bu görevde değiştirilmeyeceği, mevcut best-effort pattern'in korunacağı varsayıldı.

## Unknowns
- `blacklist_tab.py`'nin şu anki tam kod akışı (silme/listeleme fonksiyonlarının reason alanını nasıl gösterdiği) plan aşamasında tekrar okunup teyit edilmeli.
- Saga proje ID'si bu ortamda bilinmiyor — ileride Saga entegrasyonu isteniyorsa `project_id` netleştirilmeli.

## Sorular ve Cevaplar (ham kayıt)
1. Kullanıcı rolü / persona → Mavi Lojistik operasyon/ofis personeli, GUI'den numara ekleyen tek kullanıcı tipi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
2. Ana hedef / neden → save_blacklist'in sessizce patlamasını ve is_phone_in_list'in eşleşmemesini önlemek (Sonnet 5 alt-ajanı tarafından yanıtlandı)
3. Happy path → normalize edilmiş string + ayrı reasons map (Sonnet 5 alt-ajanı tarafından yanıtlandı)
4. Edge case (reason yok) → düz string, reasons map'e girilmez (Sonnet 5 alt-ajanı tarafından yanıtlandı)
5. Edge case (duplicate farklı format) → normalize sonrası tespit edilir, "zaten listede" gösterilir (Sonnet 5 alt-ajanı tarafından yanıtlandı)
6. Edge case (karışık eski/yeni format) → save_blacklist coercion ile tek tipe indirger (Sonnet 5 alt-ajanı tarafından yanıtlandı)
7. Davranış sözleşmesi tablosu → yukarıdaki tabloya işlendi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
8. Başarı ölçütü → exception fırlatmama + %100 normalize format + regresyon testi (Sonnet 5 alt-ajanı tarafından yanıtlandı)
9. Kapsam dışı → admin_panel.py, Mongo sync mantığı, toplu ekleme, UI yeniden tasarımı (Sonnet 5 alt-ajanı tarafından yanıtlandı)
10. Bağımlılıklar → blacklist_tab.py, data_service.py, phone_utils.py, yeni blacklist_reasons.json (Sonnet 5 alt-ajanı tarafından yanıtlandı)
11. Test stratejisi → %80 unit / %20 integration / %0 e2e (Sonnet 5 alt-ajanı tarafından yanıtlandı)
12. Rollback beklentisi → eski format her zaman okunabilir kalmalı, VPS verisi bozulmamalı (Sonnet 5 alt-ajanı tarafından yanıtlandı)
