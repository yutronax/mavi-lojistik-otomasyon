# Plan — deepseek-balance-diff-maliyet-hesaplama
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/api/admin_panel.py | `_check_deepseek_balance_once` zaten doğru veriyi (`balance_usd`) dönüyor ama sonucu sadece cache'liyor (satır 231-259). `_refresh_deepseek_balance` (satır 261-272) döngüsüne, yeni okuma ile bir önceki BİLİNEN başarılı okumayı karşılaştırıp farkı hesaplayan ve `deepseek_balance_history.json`'a append eden bir adım eklenecek. `/status` handler'ı (satır 220-226) yeni bir `deepseek_real_spend` alanı dönecek şekilde genişletilecek. | medium — canlıda 15dk'da bir çalışan bir arka plan thread'i değiştiriliyor, hatalı bir mantık PM2 sürecini crash ettirmemeli (mevcut `except Exception` deseni korunmalı) |

## New Files
| File | Purpose |
|------|---------|
| data/deepseek_balance_history.json | Ardışık başarılı balance okumaları ve hesaplanan farkları saklayan append-only liste. Her kayıt: `{"t_prev": iso, "t_curr": iso, "balance_prev": float, "balance_curr": float, "spend_usd": float, "top_up_detected": bool, "gap": bool}`. `data/ai_spend_history.json` formatına (liste içinde dict, ISO timestamp) paralel bir yapı — tutarlılık için. |

## Dependencies
- `_check_deepseek_balance_once(api_key, threshold_usd=5.0)` — DEĞİŞTİRİLMİYOR, dönüş şekli (`{"available", "balance_usd", "low"}`) aynen korunuyor; yeni mantık bu fonksiyonun ÇAĞIRANI (`_refresh_deepseek_balance`) tarafında eklenecek.
- `_atomic_write(path, content)` (admin_panel.py:144-149) — yeni history dosyasına atomik yazmak için bu mevcut helper kullanılacak (dosyaya özel yeni bir yazma deseni İCAT EDİLMEYECEK, `json.dumps(..., ensure_ascii=False, indent=2)` + `_atomic_write` deseni GROUPS_PATH/UNPROCESSED_PATH'te olduğu gibi tekrarlanacak).
- `PROJECT_ROOT` sabiti (admin_panel.py:34) — yeni `DEEPSEEK_BALANCE_HISTORY_PATH = os.path.join(PROJECT_ROOT, "data", "deepseek_balance_history.json")` bu desene uyacak (not: `text_gen_parser.py`'nin `os.getcwd()` kullanımından FARKLI ve daha doğru — admin_panel.py zaten PROJECT_ROOT kullanıyor, bu tutarlılık korunacak).
- `logger` (admin_panel.py modül seviyesinde tanımlı, satır ~258'de zaten `logger.error` ile kullanılıyor) — history dosyasına yazma hatası bu logger ile loglanacak (ATDD davranış sözleşmesi satır 5: yazma hatası sistemi çökertmemeli).
- Global state: mevcut `_deepseek_balance_cache` (satır 231) yanına, en son BİLİNEN başarılı okumayı (available=True/False olan, "unknown" OLMAYAN) tutan ayrı bir global (`_last_known_balance`) eklenecek — "unknown" okumaları bu referansı GÜNCELLEMEZ (AC-3 gap mantığı bunu gerektiriyor).

## Migration Required?
Hayır — yeni bir JSON dosyası (şema/DB migration değil), mevcut hiçbir
dosyanın formatı değişmiyor. Proje SQLite/ORM kullanmıyor (JSON dosya
tabanlı), migration kavramı bu projede uygulanamaz.

## Restart Kurtarma (atdd.md Unknowns'da işaretlenmiş açık soru — burada karara bağlanıyor)
`text_gen_parser.py`'deki `_init_hourly_counter_from_file()` (satır 65-85)
PM2 restart sonrası mevcut saatin harcamasını dosyadan yeniden yükleyen
BİREBİR AYNI problemi zaten çözmüş bir örnek — aynı desen izlenecek:
`_refresh_deepseek_balance` başlarken, `deepseek_balance_history.json`
dosyası varsa son kaydın `balance_curr` + `t_curr` değerini `_last_known_balance`
referansı olarak yükleyecek (dosya yoksa veya boşsa referans `None` kalır →
AC-4'teki "ilk okuma" davranışı zaten bunu karşılıyor, ekstra kod dalı
gerekmiyor).

## Risks
(atdd.md'den taşınan + planlama sırasında netleşenler)
- Tek hesap/tek API key varsayımı — değişmedi, koddan doğrulanamaz,
  ATDD'de zaten varsayım olarak işaretli.
- Arka plan thread'i değişiyor — `_refresh_deepseek_balance`'ın `while True`
  döngüsü içine eklenecek yeni mantık, MEVCUT `_check_deepseek_balance_once`
  çağrısını veya `_deepseek_balance_cache` güncellemesini BOZMAMALI (geriye
  dönük uyumluluk: `/status`'u zaten tüketen bir mobil panel/frontend var,
  `deepseek_balance` alanının şekli DEĞİŞMEMELİ, sadece yeni alan EKLENMELİ).
- `_atomic_write` her çağrıda `.tmp` dosyası + `os.replace` yapıyor — 15
  dakikada bir çalıştığı için I/O maliyeti ihmal edilebilir (ATDD'nin
  performans varsayımıyla tutarlı).

## Open Questions
Yok — atdd.md'nin Unknowns bölümündeki tek açık soru (restart kurtarma)
yukarıda `text_gen_parser.py`'deki mevcut desenle karara bağlandı, Sonnet 5
alt-ajanına dispatch gerekmiyor.
