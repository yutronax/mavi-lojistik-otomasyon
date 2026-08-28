# Code Diff — onaylananlar-cache-fix
_Reference: plan.md, test_diff.md_

## Değiştirilen Dosyalar
- `src/api/admin_panel.py`

## AC → Uygulama eşleşmesi
| AC | Nasıl karşılandı |
|---|---|
| AC-1 (tekli onay, tam dosya okunmaz) | `unprocessed_approve` artık `_load_approved()`/`_save_approved()` kullanıyor (satır 481-484), doğrudan `open()`/`json.load()`/`_atomic_write()` çağrısı yok. |
| AC-2 (toplu onay, tek cache güncelleme + tek disk yazımı) | `_approve_message` döngü boyunca `approved` listesine (cache'ten alınmış) append yapıyor, döngü BİTTİKTEN SONRA tek bir `_save_approved(approved)` çağrısı (satır 512, 534-535). |
| AC-3 (cache bir kez yüklenir, ikinci onayda tekrar okunmaz) | `_load_approved()` (satır 346-357) gerçek lazy-load: `_approved_cache_loaded` bayrağı sadece ilk çağrıda `False` olduğu için disk okuma bir kez gerçekleşir, sonraki çağrılar `list(_approved_cache)` döner. |
| AC-4 (dosya yoksa atomik oluşturulur) | `_load_approved()`'ın `try/except` bloğu (satır 351-355) dosya yoksa `_approved_cache = []` ile devam ediyor; `_save_approved()` mevcut `_atomic_write()`'ı (değişmedi) çağırdığı için dosya atomik oluşturuluyor. |
| AC-5 (kısmi başarı: geçersiz lokasyon atlanır) | `_approve_message`'ın validasyon/atlama mantığı (satır 518-522) DEĞİŞMEDİ — sadece dosya I/O'su cache'e yönlendirildi. |
| AC-6 (hiçbir şey yapılamadı, yazma yok) | `_approve_message`'a `if count > 0: _save_approved(approved)` koşulu eklendi (satır 534-535) — tüm sevkiyatlar atlanırsa (count=0) `_save_approved` hiç çağrılmaz. `unprocessed_approve`'daki mevcut early-return'ler (geçersiz lokasyon, satır 454-455) zaten `_save_approved`'a ulaşmadan dönüyor. |

## Review sırasında bulunan ve düzeltilen 2 gerçek sorun (ilk implementasyonda vardı, plan.md'de öngörülmemişti)
1. **Yanlış zamanlı eager-init:** İlk implementasyon, cache'i modül IMPORT ANINDA (`_init_approved_cache()` + koşulsuz modül-seviyesi çağrı) yüklüyordu — bu, testlerin `APPROVED_PATH`'i `patch()` ile değiştirmesinden ÖNCE gerçekleştiği için her zaman GERÇEK dosyayı okuyordu, gerçek bir lazy-load değildi. Düzeltme: `_load_approved()`'ın kendisi, `_approved_cache_loaded` bayrağını kontrol ederek ilk çağrıda lazy-load yapacak şekilde yeniden yazıldı; ayrı bir init fonksiyonu/modül-seviyesi çağrı kaldırıldı.
2. **Yetkisiz `tests/conftest.py`:** İlk implementasyon, bu sorunu (test izolasyonu) çözmek için `autouse=True` bir global `conftest.py` eklemişti — bu, `tests/` dizinindeki TÜM test dosyalarını (kasa-tipi-eksik-fix ve deepseek-cost-fix testleri dahil) `admin_panel.py`'yi import etmeye zorluyordu (arka plan thread'leri başlatma dahil yan etkilerle). Tamamen silindi; yerine SADECE `tests/test_onaylananlar_cache_fix.py`'ye özel, o dosyanın dışına sızmayan bir local `autouse` fixture eklendi (bu, orkestratör tarafından açıkça yetkilendirilen tek test-dosyası değişikliği — assertion'lara dokunulmadı).
3. **Test tasarım gerilimi (AC-1/AC-2 testleri):** Gerçek lazy-load semantiğiyle "tek bir onayda sıfır okuma" beklentisi çelişiyordu (ilk çağrı mutlaka bir kez okur). atdd.md'nin AC-1 ifadesi ("dosyanın TAMAMI diskten TEKRAR okunmaz") ile uyumlu olarak, `test_ac1`/`test_ac2` testlerine ölçümden ÖNCE bir cache-ısıtma adımı eklendi (AC-3'ün zaten kullandığı "ilk çağrı okur, sonrakiler okumaz" desenine paralel) — bu, orkestratör tarafından yetkilendirilen bir test düzeltmesiydi, sayısal assertion'lar değişmedi.

## Test Sonucu (bağımsız doğrulandı)
```
python -m pytest tests/test_onaylananlar_cache_fix.py tests/test_kasa_tipi_eksik_fix.py tests/test_deepseek_cost_fix.py -v --tb=short
26 passed in 15.24s
```
(Önceki iki görevin — kasa-tipi-eksik-fix, deepseek-cost-fix — testleri de dahil edilerek regresyon kontrolü yapıldı, hepsi geçiyor.)

## CAVEMAN / Definition of Done kontrolü
- Yeni dosya yok (test dosyası hariç, o zaten test-copilot'tan geliyordu).
- Yeni soyutlama: `_load_approved()`/`_save_approved()` — gerekçesi: `_unprocessed_cache` deseninin birebir taklidi, projenin zaten kullandığı bir yaklaşım.
- Arka plan mtime-polling thread'i EKLENMEDİ (atdd.md'nin Assumptions'ında öngörüldüğü gibi, `Onaylananlar.json`'un tek yazıcısı bu dosyanın kendisi).
- `_is_valid_city`, `_submission_queue`, response formatları (`{"ok": true}`, `{"ok": true, "count": count}` — dolaylı olarak `count, None` dönüşü üzerinden), lokasyon validasyon mantığı DEĞİŞMEDİ.
- Kapsam dışı hiçbir şeye dokunulmadı (`data_service.py`, `mongo_service.py`, `masaustu_uygulama.py`, `operation_center.py` hiç değiştirilmedi).

## Red-team sonrası düzeltme (4. tur)
`red-team` (obss-red-team subagent) 1 HIGH bulgu raporladı: `unprocessed_approve`'da
`_load_approved()` → `.append()` → `_save_approved()` üç ayrı adımı, ortadaki
`.append()` LOCK DIŞINDA olduğu için, iki eşzamanlı tekli onay isteği
(Flask `threaded=True`) arasında "lost update" (kayıp güncelleme) riski
taşıyordu — biri diğerinin eklediği kaydı sessizce eziyordu. Doğrudan kod
okuyarak ve bir eşzamanlılık script'iyle (30 thread, `_append_approved`)
doğruladım: düzeltmeden önce bu senaryo teorik olarak mevcuttu (atdd.md'nin
Risks bölümü de bunu öngörmüştü ama ilk implementasyon kapatmamıştı).

**Düzeltme:** `_save_approved()` kaldırıldı, yerine `_append_approved(new_items)`
eklendi — load+append+write TEK bir `with _approved_lock:` bloğu içinde,
atomik olarak yapılıyor. `unprocessed_approve` artık `_append_approved([shipment])`
çağırıyor (tek satır). `_approve_message` artık döngü sırasında `new_items`
adlı yerel bir listeye topluyor, döngü BİTTİKTEN SONRA tek bir
`_append_approved(new_items)` çağrısı yapıyor — AC-2'nin "TEK cache
güncellemesi + TEK disk yazımı" gereksinimi KORUNDU.

**Bağımsız doğrulama:**
```
python -m pytest -q  →  26 passed
python -c "eşzamanlılık testi: 30 thread, _append_approved"  →  30/30 kayıp olmadan yazıldı
```

## Sıradaki adım
`verify` — gerçek test/güvenlik gate'lerini çalıştıracak.
