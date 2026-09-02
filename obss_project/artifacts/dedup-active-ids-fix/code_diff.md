# Code Diff — dedup-active-ids-fix
_Reference: plan.md, test_diff.md_

## Değiştirilen Dosya
- `src/parsers/veri_cekici_ayristirici.py`

## AC → Uygulama eşleşmesi
| AC | Nasıl karşılandı |
|---|---|
| AC-1 (sadece ilçe → kalıcı işaretlenmeli) | `save_results`'taki `has_valid_shipment` kontrolü (satır 926) `nereden_ilce`/`nereye_ilce` alanlarını da kontrol edecek şekilde genişletildi — `process_message_task`'ın kendi il/ilçe kriteriyle tutarlı hale getirildi. |
| AC-2 (sıra: mark önce, active_ids temizliği sonra) | Zaten doğru çalışıyordu (mevcut `save_results` içi sıra), değiştirilmedi. |
| AC-3 (exception'da da kalıcı işaretle) | `_task_wrapper`'ın `except` bloğuna (satır 260-263) `mark_id_handled(msg_id)` çağrısı eklendi, kendi içinde ayrıca `try/except` ile korunuyor (işaretleme hatası ana akışı bozmasın diye). |
| AC-4/AC-5 (regresyon yok) | `add_to_processing_queue`'nun active_ids/body_hash kontrolleri değiştirilmedi. |

## Test Sonucu (bağımsız doğrulandı)
```
python -m pytest -q
48 passed in 19.89s
```
(Önceki tüm görevlerin testleri dahil, regresyon kontrolü yapıldı.)

## CAVEMAN / Definition of Done kontrolü
- Yeni dosya/fonksiyon yok, sadece 2 satırlık ve 4 satırlık iki nokta değişikliği.
- Kapsam dışı hiçbir şeye dokunulmadı.
- Test dosyasına dokunulmadı.

## Sıradaki adım
`verify` — gerçek test/güvenlik gate'lerini çalıştıracak. Deploy sonrası
canlı log gözlemi (AC-6, atdd.md'de belirtildi) ayrıca yapılacak.
