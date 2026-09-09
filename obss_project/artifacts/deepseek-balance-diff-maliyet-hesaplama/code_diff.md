# Code Diff — deepseek-balance-diff-maliyet-hesaplama

> Codex kotası dolu; bu task'ta test/implementasyon istisnai olarak Claude
> tarafından yazıldı, kullanıcı onaylıdır (bkz. `saga` skill Bölüm C).

## Değiştirilen Dosya
`src/api/admin_panel.py` — +117/-2 satır.

## Yeni Semboller
- `DEEPSEEK_BALANCE_HISTORY_PATH` — `PROJECT_ROOT`'a göre sabit yol (plan.md'de
  onaylanan desene uygun, `text_gen_parser.py`'nin `os.getcwd()` kullanımından
  farklı ve daha doğru — `admin_panel.py` zaten `PROJECT_ROOT` kullanıyordu).
- `_compute_balance_diff(prev_balance, curr_result, t_prev, t_curr)` — saf
  fonksiyon, dosya I/O yok. AC-1/2/3/4'ün tamamının mantığı burada.
- `_append_deepseek_balance_history(entry)` — mevcut `_atomic_write` helper'ı
  kullanılarak history dosyasına append; yazma hatası loglanır, dışarı
  fırlatılmaz (davranış sözleşmesi satır 5).
- `_load_last_known_deepseek_balance()` — restart-sonrası kurtarma; dosyadaki
  en son `gap=False` kaydı bulur (ara "unknown" kayıtları atlar).
- `_get_deepseek_real_spend()` — `/status` için son kaydın `spend_usd`'sini
  döner, son kayıt gap ise veya history boşsa `None` (0 ile karıştırılmaz).

## Değiştirilen Semboller
- `_refresh_deepseek_balance()` döngüsü: artık her okumadan sonra
  `_compute_balance_diff` çağırıp sonucu (varsa) history'e yazıyor ve
  referansı (`prev_balance`/`prev_ts`) güncelliyor. **`_check_deepseek_balance_once`
  ÇAĞRILMA ŞEKLİ VE DÖNÜŞ FORMATI DEĞİŞMEDİ** — mevcut `_deepseek_balance_cache`
  ataması aynen korundu (geriye dönük uyumluluk, plan.md'nin riskiydi).
- `/api/status` (`status()`): `deepseek_balance` alanı DEĞİŞMEDİ, sadece yeni
  `deepseek_real_spend` alanı eklendi.

## Kasıtlı Olarak Değiştirilmeyenler
- `data/ai_spend_history.json` ve onu yazan `text_gen_parser.py` kodu —
  ATDD'nin "Kapsam Dışı" kararı gereği dokunulmadı, iki kaynak paralel duruyor.
- `_check_deepseek_balance_once`'ın "unknown" / timeout / eksik-key davranışı
  — mevcut testler (`test_deepseek_primary_balance_alert.py`) bunlara
  bağımlı, hiçbiri değiştirilmedi (regresyon testiyle doğrulandı).

## CAVEMAN / Definition of Done Kontrolü
- Fonksiyonlar tek sorumluluk: hesaplama (`_compute_balance_diff`) ile I/O
  (`_append_...`, `_load_...`) ayrı fonksiyonlarda — test edilebilirlik için.
- Yeni bağımlılık/kütüphane eklenmedi (`json`, `os`, `datetime`, `threading`
  zaten import edilmişti).
- Magic number yok — eşikler (top-up algılama: `diff < 0`) doğrudan ATDD'nin
  AC-2'sinden geliyor, yorum satırında referans var.
- Derin nesting yok (en fazla 2 seviye if/for).
