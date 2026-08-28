# Plan — onaylananlar-cache-fix
_Reference: atdd.md_

## Kod keşfi — atdd.md'nin bulgularını doğrulayan/netleştiren ek detaylar
- `APPROVED_PATH` (satır 46) tam olarak 2 yerde okunuyor (satır 456, 490) ve
  2 yerde yazılıyor (satır 461, 515) — ikisi de `unprocessed_approve` (satır
  414-467) ve `_approve_message` (satır 471-519) fonksiyonları içinde.
  Başka hiçbir yerde `APPROVED_PATH` referansı yok.
- `_approve_lock` (satır 469, `threading.Lock()`) sadece `_approve_message`
  içinde kullanılıyor (satır 474, `with _approve_lock:`). `unprocessed_approve`
  (tekli onay) HİÇBİR kilit kullanmıyor — atdd.md'nin Risks bölümünde
  belirtilen kilitsizlik doğrulandı.
- Mevcut `_unprocessed_cache` deseni (satır 306-338) referans olarak birebir
  aynı isimlendirme kalıbıyla taklit edilecek: `_approved_cache`,
  `_approved_lock` (yeni, `_approve_lock`'tan farklı — o onay-mantığını,
  bu cache-erişimini korur), `_load_approved()`, `_save_approved()`.
- Program başlangıcı (`if __name__ == "__main__":` bloğu, satır 1791-1794)
  zaten `_start_bg_loader()`, `_refresh_status_cache()`,
  `_schedule_daily_cleanup()`, `_start_auto_approve()` çağırıyor — aynı yere
  cache'i senkron olarak bir kez yükleyen bir çağrı (`_load_approved_cache_sync()`
  veya benzeri) eklenecek. Bu, atdd.md AC-3'ün gerektirdiği "lazy/startup'ta
  bir kez yükleme" ihtiyacını, request-handling sırasında race condition
  riski olmadan karşılıyor (ilk isteğe kadar beklemek yerine, sunucu
  dinlemeye başlamadan önce senkron yüklenir — Flask'ın `app.run()`
  çağrısından ÖNCE, mevcut diğer `_start_*()` çağrılarıyla aynı sırada).
- `_atomic_write` (satır 141-146) zaten var ve değişmeyecek — cache'in
  serialize edilmiş hali bu fonksiyona verilecek, aynen `_save_unprocessed`
  deseninde olduğu gibi.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | `unprocessed_approve` (satır 456-461) ve `_approve_message` (satır 490, 515) içindeki tam dosya oku/yaz döngüsünü cache tabanlı erişimle değiştirmek; yeni `_approved_cache`/`_approved_lock`/`_load_approved`/`_save_approved` fonksiyonlarını eklemek; başlangıç bloğuna cache'i senkron yükleyen bir çağrı eklemek. | medium |

## New Files
Yok — atdd.md'nin Kararlar'ında da netleşen CAVEMAN ilkesi gereği, mevcut
`_unprocessed_cache` deseni birebir taklit ediliyor, yeni bir dosya/modül
gerekmiyor.

## Dependencies
- Mevcut `_atomic_write(path, content)` (satır 141-146) — değişmeden
  tekrar kullanılacak.
- Mevcut `_unprocessed_cache` / `_load_unprocessed` / `_save_unprocessed`
  deseni (satır 306-338) — isimlendirme ve yapı birebir örnek alınacak
  (`_approved_cache`, `_load_approved`, `_save_approved`), AMA atdd.md'nin
  Assumptions'ında belirtildiği gibi arka plan mtime-polling thread'i
  (`_start_bg_loader` benzeri) EKLENMEYECEK — çünkü `Onaylananlar.json`'un
  tek yazıcısı bu dosyanın kendisi (kod keşfiyle doğrulandı, başka process
  yazmıyor).
- `unprocessed_approve` ve `_approve_message` fonksiyonlarının geri kalan
  mantığı (lokasyon validasyonu `_is_valid_city`, `_submission_queue.add_task`,
  response formatları) DEĞİŞMİYOR — sadece `APPROVED_PATH`'e doğrudan
  `open()`/`json.load()`/`_atomic_write()` çağrıları, yeni cache
  fonksiyonlarına yönlendirilecek.

## Migration Required?
Hayır. Disk üzerindeki `data/Onaylananlar.json`'un formatı (JSON dizisi)
değişmiyor — sadece bu dosyaya erişim deseni (kaç kez okunduğu) değişiyor.
Var olan 143MB'lık dosya, yeni kod tarafından ilk başlangıçta olduğu gibi
okunacak, hiçbir veri dönüştürme/taşıma yapılmayacak.

## Risks
_(atdd.md'den taşındı + kod keşfinde netleşenler)_
- `unprocessed_approve`'un kilitsiz olması (atdd.md'de zaten tespit edildi)
  — yeni `_approved_lock` ile cache erişimi (`_load_approved`/`_save_approved`
  içinde) korunacak, bu da bu riski dolaylı olarak kapatıyor (iki fonksiyon
  da artık aynı lock'un koruduğu cache üzerinden geçecek).
- Cache'in senkron olarak diske yazılması (atdd.md'nin Risks'inde belirtildiği
  gibi, veri kaybı riskine karşı) — `_save_unprocessed` deseniyle birebir
  aynı: `_atomic_write` çağrısı `_save_approved` içinde senkron yapılacak,
  fonksiyon dönmeden önce disk yazımı tamamlanmış olacak.
- 143MB'lık dosyanın başlangıçta senkron yüklenmesi, sunucunun ayağa
  kalkma süresini bir miktar uzatabilir (muhtemelen birkaç saniye) — bu,
  atdd.md'nin AC-3'ünün kabul ettiği bir maliyet (tek seferlik, dosya
  boyutundan bağımsız sürekli maliyetin yerine).

## Open Questions
Yok — atdd.md'nin kod keşfi zaten netleşmiş durumda (özellikle
çapraz-process senkronizasyon ihtiyacının olmadığı ve kapsamın SADECE
`src/api/admin_panel.py` olduğu doğrulandı). Haiku alt-ajanına dispatch
edilecek açık bir soru yok.

## Vision-test notu
Bu görev bir backend I/O optimizasyonu — hiçbir web UI/HTML/CSS dosyasına
dokunmuyor. `verify` adımında gate 11 (vision-test) N/A olacak.
