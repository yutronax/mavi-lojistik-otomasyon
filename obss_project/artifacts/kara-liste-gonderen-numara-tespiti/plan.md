# Plan — kara-liste-gonderen-numara-tespiti
_Reference: atdd.md_

## Kararlar (Unknown'ları çözen kod bulguları)
- **`message_info.sender_number`'ın kaynağı netleşti (AC-6 çözüldü):** Kod
  incelemesi sonucu (`Read`/`Grep`, sub-agent dispatch'e gerek kalmadı —
  cevap kod içinde açıkça bulundu) — [veri_cekici_ayristirici.py:878](src/parsers/veri_cekici_ayristirici.py:878)
  ve [:903](src/parsers/veri_cekici_ayristirici.py:903)'te
  `'sender_number': res['original_msg'].get('from')` olarak set ediliyor.
  Bu, GÖVDEDEN regex ile çıkarılan bir numara DEĞİL — gerçek gönderen
  kimliği (`from`/JID, Baileys'te `participantAlt || participant`
  zincirinin sonucu). Kanıt: `data/Onaylananlar.json`'da
  `"sender_number": "76025719423128@lid"` gibi kayıtlar var — bu bir LID,
  hiçbir ilan sahibinin telefon numarası olamaz, sadece gönderen JID'i
  olabilir. **Sonuç: `sender_number` blacklist kontrolünde güvenle
  kullanılabilir, AC-6'daki "kullanılmamalı" riski ORTADAN KALKTI.**
- `phone_utils.normalize_phone`/`get_phone_variants`, `\D` (rakam olmayan)
  karakterleri temizliyor — `"...@lid"` gibi bir string'den sadece rakamlar
  kalır (14+ haneli), bu hiçbir zaman gerçek 10/11/12 haneli blacklist
  formatıyla çakışmaz (yanlış pozitif riski yok, sadece eşleşme
  sağlanamıyor — bilinen sınırlama, atdd.md'de zaten kabul edilmiş).

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| [src/services/data_service.py](src/services/data_service.py:212) | AC-1: blacklist alan seçim sırası `message_info.sender` (isim) yerine `message_info.sender_number` (gerçek JID) okumalı | low |
| [src/services/mongo_service.py](src/services/mongo_service.py:128) | AC-2: aynı bug, MongoDB okuma yolu | low |
| [src/parsers/veri_cekici_ayristirici.py](src/parsers/veri_cekici_ayristirici.py:505) | AC-4/5: `sender_raw` boşsa (satır 505-510 ve 704-709) sessizce geçiliyor — WARN log eklenecek | low |

## New Files
| File | Purpose |
|------|---------|
| tests/test_blacklist_sender_number_field.py | AC-1/2/7: `data_service`/`mongo_service` blacklist filtresinin `sender_number` alanını doğru okuduğunu ve normalizasyon varyantlarını (0/90/+90) doğru eşleştirdiğini test eder |
| tests/test_orchestrator_missing_sender_warning.py | AC-4/5: `add_to_processing_queue`'da gönderen tespit edilemediğinde WARN loglandığını, mesajın yine de işlendiğini (fail-open) doğrular |

## Dependencies
- `src/utils/phone_utils.py` (`is_phone_in_list`, `get_phone_variants`,
  `normalize_phone`) — DOKUNULMUYOR, sadece test edilecek (mevcut
  normalizasyon zaten `@lid`/`@s.whatsapp.net` gibi son ekleri `\D` temizliği
  ile güvenli şekilde eziyor).
- `DataService.load_blacklist()` — mevcut, değişmiyor.
- `sidecar/bridge.js:82`'deki `participantAlt || participant || from`
  zinciri — DOKUNULMUYOR (önceki görevde red-team onaylı, regresyon testi
  kapsamında sadece doğrulanacak).

## Migration Required?
Hayır — şema/veri migrasyonu yok, sadece hangi mevcut JSON/Mongo alanının
okunduğunu değiştiren düz kod değişikliği (`item['message_info'].get('sender')`
→ `item['message_info'].get('sender_number')`, öncelik sırasıyla).

## Değişiklik Detayı (code-copilot için)

**data_service.py satır 212-214** — mevcut:
```python
sender_num = item.get('phone') or item.get('sender')
if not sender_num and 'message_info' in item:
    sender_num = item['message_info'].get('sender')
```
yeni:
```python
sender_num = item.get('phone')
if not sender_num and 'message_info' in item:
    sender_num = item['message_info'].get('sender_number')
if not sender_num:
    sender_num = item.get('sender')
```
(`item.get('sender')` en sona, son çare fallback olarak kalıyor — bazı eski
kayıtlarda `message_info` hiç olmayabilir; ama `message_info.sender_number`
her zaman `message_info.sender`'dan (isim) ÖNCE denenmeli.)

**mongo_service.py satır 128-130** — aynı değişiklik, `doc` üzerinden.

**veri_cekici_ayristirici.py satır 505-510 ve 704-709** — `if sender_raw:`
bloğuna kardeş bir `else` eklenecek:
```python
else:
    logger.warning(f"[WARN] Gönderen kimliği tespit edilemedi (mid={mid}) — blacklist kontrolü atlandı, mesaj işlenmeye devam ediyor")
```

## Risks
- `item.get('sender')`'ı tamamen SİLMEK yerine son fallback olarak
  bırakmak bilinçli bir karar: eski/geçmiş kayıtlarda `message_info` yoksa
  bu satır regresyon yaratmasın diye. Ama bu, isim string'inin YİNE DE bir
  "numara" gibi denenmesi riskini taşıyor (zaten mevcut davranış, kötüleşmiyor).
- `is_phone_in_list` LID'leri hiç yakalayamıyor (bilinen sınırlama,
  atdd.md'de kabul edilmiş) — bu plan bunu ÇÖZMÜYOR, sadece mevcut alan
  okuma bug'ını düzeltiyor. `participantAlt` yoksa blacklist hâlâ etkisiz
  kalabilir.

## Open Questions
Yok — AC-6'daki tek açık soru (sender_number kaynağı) kod incelemesiyle
kesin olarak çözüldü, sub-agent dispatch'ine gerek kalmadı.
