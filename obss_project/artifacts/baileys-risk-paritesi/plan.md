# Plan — baileys-risk-paritesi
_Reference: atdd.md_

## Kararlar (atdd.md'nin Unknowns'unu netleştiriyor)

1. **Log formatı: JSON Lines (`sidecar/risk_events.log`).** Her satır tek bir
   olay: `{"type":"disconnect","statusCode":440,"ts":"2026-09-01T..."}`
   veya `{"type":"message","count":1,"ts":"..."}`. Append-only, basit
   parse. Gerekçe: `bridge.js` zaten satır satır log basıyor, ek bir DB/
   dosya-kilitleme mekanizması gerektirmez.
2. **Retention: aktif pruning YOK bu ilk sürümde.** `risk_check.js`
   dosyayı okurken zaman penceresine göre filtreler (son 1 saat / son 7
   gün) — dosyanın kendisi kırpılmaz. Gerekçe: düşük hacim (günde birkaç
   disconnect/mesaj event'i), dosya küçük büyür; pruning ayrı bir görev
   olarak sonraya bırakılabilir (Kapsam Dışı'na eklenmeli).
3. **Mesaj hacmi: `bridge.js`'in zaten bildiği `converted.length` her
   `postToWebhook` çağrısında `risk_events.log`'a da yazılacak.** Ayrı bir
   sayaç mekanizması gerekmiyor, mevcut kod yoluna tek satır ekleme.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `sidecar/bridge.js` | `connection.update`'teki `close` dalına ve `postToWebhook` başarı yoluna `risk_events.log`'a JSON-line append eden 1-2 satır eklenecek (AC-1 için ham veri kaynağı) | low — sadece ek log yazımı, mevcut akışı değiştirmiyor |

## New Files
| File | Purpose |
|------|---------|
| `sidecar/risk_events.log` | Runtime'da `bridge.js` tarafından oluşturulan veri dosyası (kod değil) — `.gitignore`'a eklenmeli |
| `sidecar/risk_check.js` | CLI aracı: `risk_events.log`'u okuyup AC-1..AC-5'teki 5 senaryoyu (happy/veri yok/high risk/kısmi veri/kaynak yok) hesaplayıp yazdırır |

## Dependencies
- `sidecar/bridge.js`'in mevcut `connection.update` ve `messages.upsert` event handler'ları (değişmeyecek akış, sadece ek log satırı)
- Node'un yerleşik `fs`/`readline` modülleri (yeni bağımlılık gerekmiyor)

## Migration Required?
Hayır — kod/şema değişikliği yok, sadece yeni bir runtime log dosyası.

## .gitignore Güncellemesi
`sidecar/.gitignore`'a `risk_events.log` eklenecek (diğer `poc_*`/`bridge_*` log'ları gibi, runtime verisi commit'lenmemeli).

## Risks
atdd.md'deki riskler aynen geçerli, ek olarak:
- Log dosyası pruning'i olmadan uzun vadede büyüyebilir — bu bilinen bir trade-off, Kapsam Dışı'na netçe yazılacak (ileride ayrı bir "log rotation" görevi gerekebilir).
- `risk_check.js`'in zaman penceresi hesaplamaları (son 1 saat / son 7 gün) sistem saatine bağlı — saat dilimi/DST gibi kenar durumlar bu görevde ele alınmayacak (küçük ölçekli iç araç, kritik değil).

## Open Questions
Yok — atdd.md'nin 3 Unknowns'u yukarıdaki Kararlar bölümünde doğrudan çözüldü (düşük riskli, geri alınabilir mühendislik kararları; kullanıcı onayı gerektiren bir belirsizlik kalmadı).
