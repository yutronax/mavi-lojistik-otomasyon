# Plan — deepseek-primary-balance-alert
_Reference: atdd.md_

## Kod keşfi
- `text_gen_parser.py`: model zinciri TAM OLARAK 2 yerde tanımlı:
  - Satır 271 (Stage 1, konum çıkarma): `models_to_try = ['openai/gpt-oss-20b', 'deepseek-v4-flash']`
  - Satır 445 (Stage 2, tam parse): `models_to_try = ['openai/gpt-oss-20b', self.model_robust] + self.fallback_models` (`self.model_robust = 'deepseek-v4-pro'`, satır 68; `self.fallback_models = ['deepseek-v4-flash']`, satır 71)
  Her iki listenin de SADECE SIRASI değişecek — DeepSeek modelleri öne, Groq sona.
- `src/api/admin_panel.py` satır 169-221: `_status_cache` (global dict) + `_refresh_status_cache()` (arka plan thread, HER 8 SANİYEDE BİR `_status_cache = result` ile TÜM dict'i DEĞİŞTİRİYOR, sadece "service"/"system" anahtarlarını biliyor). **ÖNEMLİ BULGU**: Eğer bakiye bilgisini bu AYNI dict'e eklersem, `_refresh_status_cache`'in 8 saniyelik döngüsü onu SİLER (her iterasyonda `result = {"service": ...}` ile TAZE bir dict başlatılıyor). Bu yüzden bakiye cache'i AYRI bir global değişken (`_deepseek_balance_cache`) olmalı — dosyanın zaten kullandığı desen (`_unprocessed_cache`, `_approved_cache`, `_status_cache` hepsi birbirinden bağımsız global'ler).
- `src/api/admin_panel.py` satır 700, 735: harici HTTP çağrıları için `urllib.request`/`urllib.error` kullanılıyor (whapi.cloud health-check örneği) — `requests` paketi kurulu olsa da bu DOSYADA hiç kullanılmıyor. CAVEMAN: mevcut deseni takip et, `urllib.request` kullan, yeni bir HTTP kütüphanesi/import deseni icat etme.
- `.env`'de `DEEPSEEK_API_KEY` zaten tanımlı (önceki oturumlarda doğrulandı).

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| text_gen_parser.py | Satır 271 ve 445'teki `models_to_try` listelerinin SIRASINI değiştir (DeepSeek önce, Groq sonra). | low |
| src/api/admin_panel.py | Yeni `_deepseek_balance_cache` global + `_refresh_deepseek_balance()` arka plan thread'i (satır ~169-221 civarına, `_refresh_status_cache`'in hemen yanına); `/api/status` route'u (satır 217-221) yanıtına `deepseek_balance` alanı eklenecek; başlangıç bloğuna (satır ~1791 civarı) yeni thread'in `_refresh_deepseek_balance()` çağrısı eklenecek. | medium |

## New Files
Yok.

## Dependencies
- `urllib.request`/`urllib.error` (stdlib, zaten dosyada kullanılıyor).
- `os.getenv("DEEPSEEK_API_KEY")` (zaten `.env`'de mevcut, başka yerlerde de okunuyor).
- Mevcut `threading.Thread(..., daemon=True)` deseni (satır 214, `_refresh_status_cache`'in kendisi).

## Migration Required?
Hayır.

## Risks
_(atdd.md'den taşındı + kod keşfinde netleşenler)_
- `_status_cache`'in 8 saniyelik tam-üzerine-yazma davranışı (yukarıda
  açıklandı) — AYRI bir global cache kullanılarak bu risk tamamen
  ortadan kaldırılıyor, ekstra bir düzeltme gerekmiyor.
- Model sırası değişikliğinin maliyet etkisi (atdd.md'nin Risks'inde
  zaten not düşüldü) — kod tarafında ölçülemez, sadece gözlemlenebilir
  (production'da `_track_spend` logları üzerinden).

## Open Questions
1. **Bakiye kontrol periyodu**: atdd.md 15 dakika öneriyor. `_status_cache`'in
   8 saniyelik döngüsünden ÇOK daha seyrek olmalı (bakiye sık değişmiyor,
   DeepSeek API'sine gereksiz yük bindirmemek için). **Öneri: 15 dakika
   (900 saniye)** — atdd.md'nin kendi önerisiyle tutarlı, onaylanmış kabul
   edilebilir.
2. **Bakiye eşiği**: atdd.md $5 öneriyor ama kesinleşmedi. **Öneri: $5**
   — DeepSeek'in ucuz fiyatlandırması (token başına $0.27-1.10/1M)
   göz önüne alındığında, $5 birkaç günlük kullanım payı sağlar, makul
   bir erken-uyarı eşiği.
3. **DEEPSEEK_API_KEY birden fazla anahtar mı (rotasyon) yoksa tek mi?**
   Kod keşfinde `_get_deepseek_client()`'in `os.getenv("DEEPSEEK_API_KEY")`
   kullandığı (satır 84-87, `text_gen_parser.py`) doğrulandı — TEK bir
   anahtar, Groq'taki gibi bir rotasyon havuzu YOK. Bakiye kontrolü de
   aynı TEK anahtarı kullanacak — bu, plan aşamasında netleşen bir kod
   gerçeği, kullanıcıya sorulacak bir şey değil.

Yukarıdaki 1 ve 2, düşük riskli/tersine çevrilebilir varsayılan değerler
(config sabiti, kolayca değiştirilebilir) — Haiku alt-ajanına dispatch
etmek yerine burada makul varsayılanlarla karara bağlandı, code-copilot
bu değerleri kullanacak.
