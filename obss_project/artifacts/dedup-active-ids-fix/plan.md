# Plan — dedup-active-ids-fix
_Reference: atdd.md_

## Kod keşfi — mevcut durum (satır numaraları teyit edildi)
- `_task_wrapper` (satır 249-274): `process_message_task`'ı çağırır,
  sonucu `save_results([result])`'a iletir; `finally` bloğu (satır
  260-274) `active_ids`/`active_body_hashes`'ten KOŞULSUZ çıkarır.
- `add_to_processing_queue` (satır 428-...): mesajları filtreleyip
  `active_ids`/`active_body_hashes` kontrolüyle kuyruğa ekler — bu kısım
  ZATEN DOĞRU çalışıyor (atdd.md AC-4/AC-5), DOKUNULMAYACAK.
- `process_message_task` (satır 710-...): AI parse + filtreleme;
  "FILTER: Empty Route Check" (atdd.md'de alıntılanan satırlar) bir
  sevkiyatı `nereden_il or nereden_ilce` VE `nereye_il or nereye_ilce`
  varsa geçerli sayıyor.
- `save_results` (satır 802-...): `has_valid_shipment` hesaplaması SADECE
  `nereden_il`/`nereye_il` (il) alanlarına bakıyor — `process_message_task`'ın
  il/ilçe kriteriyle TUTARSIZ. `mark_id_handled()` çağrısı SADECE
  `save_payload` içindeki key'ler için yapılıyor (atdd.md'de alıntılanan
  satır ~938 civarı).

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| src/parsers/veri_cekici_ayristirici.py | (1) `save_results`'taki `has_valid_shipment` kontrolünü `process_message_task`'ın il/ilçe kriteriyle TUTARLI hale getirmek (AC-1); (2) `_task_wrapper`'ın `except` bloğunda da `mark_id_handled` çağrısı eklemek (AC-3); (3) `finally` bloğunun `active_ids` çıkarma sırasını `mark_id_handled` GARANTİSİNDEN sonraya almak/garanti etmek (AC-2). | medium |

## New Files
Yok.

## Dependencies
- `self.data_service.mark_id_handled(msg_id)` — zaten var, sadece çağrı
  noktaları genişletiliyor.
- Mevcut `has_valid_shipment` mantığının YERİNE, `process_message_task`'ın
  zaten hesapladığı "geçerli sevkiyat" bilgisini YENİDEN KULLANMAK (aynı
  il/ilçe kontrolünü iki yerde FARKLI yazmak yerine) CAVEMAN'a daha uygun
  olabilir — ama bu, `process_message_task`'ın dönüş sözleşmesini
  değiştirmeyi gerektirir (örn. sonuca `has_valid_shipment: bool` alanı
  eklemek). Aşağıda Open Questions'ta karara bağlanacak.

## Migration Required?
Hayır — sadece kontrol mantığı değişiyor, veri şeması/dosya formatı
değişmiyor.

## Risks
_(atdd.md'den taşındı + kod keşfinde netleşenler)_
- `save_results`'ın il/ilçe kriterini genişletmesi, `data/onaylanmamis_ayristirilmis.json`'a
  daha önce hiç yazılmayan (sadece ilçe bilgili) kayıtların artık
  yazılmasına yol açacak — bu, panel/admin arayüzünde bu tür kayıtların
  görünürlüğünü artırır (istenen bir yan etki, atdd.md'nin hedefiyle
  tutarlı).
- `_task_wrapper`'ın `except` bloğunda `mark_id_handled` çağırmak,
  GERÇEKTEN geçici bir hatada (ör. ağ kesintisi) mesajın bir daha hiç
  denenmemesine yol açar — atdd.md'nin Risks bölümünde zaten kabul
  edilmiş bir taviz (mevcut kodun "sonsuz loop önleme" felsefesiyle
  tutarlı).

## Open Questions
1. **`save_results`'ın il/ilçe kontrolünü NASIL `process_message_task`'la
   tutarlı hale getirelim?**
   - Seçenek A (basit, önerilen): `save_results`'taki kontrolü
     `s.get('nereden_il') or s.get('nereden_ilce') or s.get('nereye_il') or s.get('nereye_ilce')`
     olarak genişletmek — `process_message_task`'a DOKUNMADAN, sadece
     `save_results`'ın kriterini eşleştirmek. CAVEMAN'a uygun, tek
     dosyada tek satır değişikliği.
   - Seçenek B (daha "doğru" ama daha invaziv): `process_message_task`'ın
     dönüş sözleşmesine `is_valid: bool` gibi bir alan eklemek,
     `save_results`'ın kendi kriterini YENİDEN HESAPLAMASI yerine bunu
     okumasını sağlamak — iki yerde aynı mantığı tekrarlamaktan kaçınır
     ama dönüş şemasını değiştirir, daha fazla test/dokunulan yüzey.
   - **Öneri: Seçenek A** — CAVEMAN ilkesine uygun, mevcut dönüş
     şemasına dokunmuyor, riski en düşük.
2. **`_task_wrapper`'ın `except` bloğunda `mark_id_handled` çağrılırken,
   `active_ids`'ten çıkarma ile aynı `finally` bloğunda mı olmalı, yoksa
   `except` bloğunun kendi içinde mi?**
   - Öneri: `except` bloğunun İÇİNDE çağrılmalı (loglamadan hemen sonra),
     `finally` bloğu (active_ids temizliği) DEĞİŞMEDEN kalır — bu, AC-2'nin
     "active_ids çıkarma, mark_id_handled'dan SONRA" sırasını doğal olarak
     sağlar (except → mark_id_handled, sonra finally → active_ids temizle).

Yukarıdaki 2 soru, düşük riskli/geri döndürülebilir kararlar — Haiku
alt-ajanına dispatch etmek yerine burada makul varsayılanlarla (A ve
"except içinde çağır") karara bağlandı, code-copilot bu kararları
kullanacak.
