# Code Diff — kara-liste-gonderen-numara-tespiti (green step)

## Değiştirilen Dosyalar (3, yeni dosya yok)
- `src/services/data_service.py` (+4/-2, satır ~212-216)
- `src/services/mongo_service.py` (+4/-2, satır ~128-132)
- `src/parsers/veri_cekici_ayristirici.py` (+12, satır ~505-514 ve ~709-717)

## AC → Implementasyon
| AC | Değişiklik |
|---|---|
| AC-1 | `data_service.py`: blacklist sırası `phone` → `message_info.sender_number` → `sender` (son çare) |
| AC-2 | `mongo_service.py`: aynı sıra değişikliği |
| AC-3 | Değişmedi (regresyon) — `veri_cekici_ayristirici.py`'nin mevcut `is_phone_in_list(sender_raw, ...)` akışı korundu |
| AC-4 | `veri_cekici_ayristirici.py`: `sender_raw` dolu ve `'@lid' in sender_raw` ise WARN log (iki yerde) |
| AC-5 | `veri_cekici_ayristirici.py`: `sender_raw` boşsa `else:` bloğunda WARN log, fail-open korunuyor (`mark_id_handled` çağrılmıyor) |
| AC-6 | Kod değişikliği yok — `sender_number`'ın JID kaynağı olduğu doğrulandı (plan.md) |
| AC-7 | Değişmedi (regresyon) — `phone_utils.py`'ye dokunulmadı |

## Doğrulama (bağımsız olarak tekrar çalıştırıldı)
```
13 passed in 0.15s
```
`git diff --stat src/`: 3 dosya, +20/-4 — plan.md'nin öngördüğü kapsamla birebir örtüşüyor, ekstra dosya/soyutlama yok.

## CAVEMAN Self-Review
- Yeni dosya: 0
- Yeni yardımcı fonksiyon/soyutlama: 0 — sadece mevcut if/else bloklarına satır ekleme
- Kapsam dışı değişiklik: yok

## Kalan Sınırlamalar (atdd.md'de zaten kabul edilmiş)
- `participantAlt` hiç sağlanmazsa (sadece LID varsa) blacklist eşleşmesi hâlâ mümkün değil — bu görev sadece WARN logu ekliyor, LID→numara çözümü yapmıyor (kapsam dışı, atdd.md'de açık).
- Whapi.cloud kanalının `from` alanı formatı bu görevde doğrulanmadı (kapsam dışı).
