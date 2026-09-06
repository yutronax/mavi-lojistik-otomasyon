# Plan — blacklist-normalize-fix
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/utils/phone_utils.py | `is_phone_in_list()` şu an `phone_list` elemanlarını hiç normalize etmeden ham string karşılaştırması yapıyor (AC-2, AC-3). Elemanlar dict (`{"phone":...,"reason":...}`) veya boşluklu/tireli string olabilir — bunları da kabul edip normalize ederek karşılaştırmalı. Mevcut `tests/test_blacklist_sender_number_field.py::test_normalization_regression_0_format_ac7` sadece düz string listesiyle test ediyor; bu davranış bozulmamalı. | medium |
| src/services/data_service.py | `save_blacklist()` içindeki `sorted(list(set(blacklist)))` çağrısı, liste içinde dict varsa `TypeError: unhashable type` ile patlıyor (try/except içinde yutuluyor → sessiz başarısızlık, AC-1). Kaydetmeden önce her elemanı coerce edip (dict→phone çıkar, reason varsa ayrı map'e taşı, phone'u `normalize_phone()` ile normalize et) tek tip düz-string listeye indirgemeli. Ayrıca yeni `load_blacklist_reasons`/`save_blacklist_reasons` yardımcı fonksiyonları eklenecek (AC-6). | medium |
| src/gui/components/blacklist_tab.py | `_add_blacklist()` girdi telefonunu hiç normalize etmiyor ve reason varsa dict, yoksa string ekliyor (karışık format kaynağı). `normalize_phone()` ile normalize edip her zaman düz string ekleyecek, reason'ı ayrı bir reasons map'ine yazacak, geçersiz uzunlukta numarayı reddedecek (AC-5) ve normalize sonrası zaten listede olan numarayı reddedip "zaten kara listede" mesajı gösterecek (AC-4) şekilde güncellenecek. `_refresh_list()`'in reason gösterimi, artık listenin düz-string+ayrı reasons map olmasına göre güncellenmeli (dict-check kod yolu kaldırılabilir ama reasons map'ten okuma eklenmeli). `_delete_blacklist()` de artık sade string karşılaştırması yapabilir (basitleşir). | low |

## New Files
| File | Purpose |
|------|---------|
| tests/test_blacklist_normalize.py | AC-1..AC-6'yı kapsayan unit + integration testler: normalize+coercion, `save_blacklist` dict/karışık girdiyle patlamama, `is_phone_in_list` normalize edilmiş/edilmemiş karşılaştırma, duplicate tespiti, VPS'teki mevcut 111-kayıt formatıyla regresyon. |

Not: `data/blacklist_reasons.json` bir "yeni dosya" değil, çalışma zamanında `save_blacklist_reasons()` ilk çağrıldığında oluşturulacak bir veri dosyası — kod deposuna dahil edilmeyecek (mevcut `data/*.json` dosyaları gibi git'te izlenen bir dosya olması gerekip gerekmediği kullanıcıya sorulmalı, bkz. Open Questions).

## Dependencies
- `src.utils.phone_utils.normalize_phone` — zaten var, `admin_panel.py`'nin doğru çalışan yolu da fiilen aynı mantığı elle uyguluyor (`"".join(c for c in ... if c.isdigit())` + 10 haneliyse `0` ekleme). Yeni kod bu var olan `normalize_phone()`'u çağırmalı, mantığı tekrar yazmamalı.
- `src.utils.phone_utils.get_phone_variants` / `is_phone_in_list` — mevcut imza korunacak, sadece `phone_list` tarafı da normalize edilecek şekilde genişletilecek (geriye dönük uyumlu: düz string listesiyle çağrılan mevcut testler bozulmamalı).
- `src.services.data_service.persistence_manager.queue_write` — `save_blacklist`'in mevcut yazma mekanizması korunacak, sadece öncesine coercion adımı eklenecek.
- `src.services.data_service_async.AsyncDataService.load_blacklist/save_blacklist` — ince `run_in_executor` sarmalayıcılar, değişiklik gerekmiyor (senkron tarafı çağırıyorlar).
- `src.api.admin_panel.py`'nin `/api/blacklist` POST normalize mantığı — değiştirilmeyecek, sadece referans/pattern olarak kullanılacak (atdd.md "Kapsam Dışı").

## Migration Required?
Hayır — şema değişikliği yok. `blacklist.json` formatı (düz string listesi) değişmiyor, sadece artık HER ZAMAN bu formatta tutarlı kalması garanti ediliyor (coercion, mevcut veriye dokunmuyor çünkü zaten o formatta). Yeni `blacklist_reasons.json` bir migration değil, opsiyonel ek bir veri dosyası; yokluğu ana filtreleme akışını etkilemeyecek (atdd.md Rollback Beklentisi).

## Risks
- (atdd.md'den taşındı) VPS'teki canlı `blacklist.json` üzerinde yanlış bir coercion adımı veri kaybına yol açabilir → test stratejisi mevcut 111-kayıt formatını sabit bir regresyon fixture'ı olarak kullanmalı, canlı dosyaya bu görev kapsamında elle dokunulmayacak.
- `blacklist_tab.py`'deki `_refresh_list()` şu an dict formatını GUI'de gösterebiliyor (satır 47-53) — reason'ı ayrı dosyaya taşırsak bu görüntüleme mantığı da güncellenmeli, yoksa mevcut (varsa) dict kayıtlar için reason görünmez hale gelebilir. Kod incelemesinde şu an prod'da dict formatlı kayıt yok (VPS doğrulandı), risk düşük ama kod değişikliği bunu unutmamalı.
- `is_phone_in_list`'in `phone_list` elemanlarını normalize ederken dict elemanları da güvenle atlaması/çıkarması gerekiyor — mevcut çağrı yerleri (`data_service.py`, `mongo_service.py`, `veri_cekici_ayristirici.py`) hep düz string listesi bekliyor, imza/davranış değişikliği onları kırmamalı.

## Open Questions (Kararlar)
1. `blacklist_reasons.json` `.gitignore`'a eklenecek, git'e dahil edilmeyecek. (Haiku alt-ajanı tarafından yanıtlandı: atdd.md bu dosyayı "opsiyonel"/çalışma-zamanında-oluşan veri olarak tanımlıyor, kalıcı proje verisi değil — diğer tracked `data/*.json` dosyalarından farklı olarak kullanıcı-girdili geçici metadata.)
2. GUI'de reason gösterimi bu görev kapsamı dışında bırakılacak — `_refresh_list()` reasons dosyasından okuma eklemeyecek, sadece düz-string kara listeyi gösterecek. (Haiku alt-ajanı tarafından yanıtlandı: atdd.md AC-2 sadece filtrelemenin çalışmasını şart koşuyor, GUI gösterimi kritik değil.)
