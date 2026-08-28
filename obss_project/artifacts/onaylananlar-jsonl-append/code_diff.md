# Code Diff — onaylananlar-jsonl-append
_Reference: plan.md, test_diff.md_

## Değiştirilen/Oluşturulan Dosyalar
- `src/api/admin_panel.py` (değiştirildi)
- `scripts/migrate_onaylananlar_to_jsonl.py` (yeni)

## AC → Uygulama eşleşmesi
| AC | Nasıl karşılandı |
|---|---|
| AC-1 (tekli onay, mevcut içerik hiç okunmaz) | `unprocessed_approve` (satır 454-457): `json.load` tamamen kaldırıldı, `with _approve_lock: with open(APPROVED_PATH, "a", ...) as f: f.write(json.dumps(shipment)+"\n")` — saf append. |
| AC-2 (toplu onay, tek dosya açma/yazma, okuma yok) | `_approve_message` (satır 485-509): döngü `new_items` yerel listesine topluyor, döngü BİTTİKTEN SONRA `if new_items:` koşuluyla TEK `with open(..., "a")` bloğu içinde tüm satırlar yazılıyor. |
| AC-3 (bellek dosya boyutundan bağımsız) | Test suite'in kendi AC-3 testi PASS; AYRICA bağımsız olarak 95.5MB/150.000 kayıtlık (gerçek production dosyasından BÜYÜK) sentetik bir dosya üzerinde doğrudan test ettim: 50 onay sonrası RSS artışı sadece **0.1MB**. |
| AC-4 (dosya yoksa otomatik oluşur) | `open(path, "a")` modu Python'da dosya yoksa otomatik oluşturur — özel bir dal gerekmiyor. |
| AC-5 (migration script, kayıpsız taşıma) | `scripts/migrate_onaylananlar_to_jsonl.py` — bağımsız olarak 500 kayıtlık sentetik bir `Onaylananlar.json` üzerinde test ettim: 500/500 kayıp olmadan taşındı, unicode (Türkçe karakterler) korundu, sıra korundu, orijinal dosya silinmedi. |
| AC-6 (kısmi başarı, geçersiz lokasyon atlanır) | `_approve_message`'ın mevcut `_is_valid_city` kontrolü (satır 491-494) DEĞİŞMEDİ — sadece I/O katmanı değişti. |
| AC-7 (hiçbir şey yapılamadı, yazma yok) | `if new_items:` koşulu (satır 506) — tüm sevkiyatlar atlanırsa dosyaya HİÇ yazılmaz. |

## Bağımsız doğrulama (kod review sırasında, sub-agent'ın raporuna ek olarak bizzat yaptığım)
1. `python -m pytest -q` (tüm proje) → **27 passed**, bağımsız tekrarlandı.
2. Kodun kendisini okudum (satır 454-513) — spesifikasyona birebir uyuyor, kapsam dışı hiçbir değişiklik yok, `_atomic_write` bu iki fonksiyondan çağrılmıyor ama fonksiyonun kendisi silinmemiş (başka yerlerde kullanılıyor).
3. Migration script'ini gerçek bir subprocess çalıştırmasıyla (500 kayıt, Türkçe karakterli) test ettim — 500/500 doğru taşındı, orijinal silinmedi.
4. **En kritik doğrulama**: 95.5MB/150.000 kayıtlık sentetik dosya üzerinde `_approve_message` çağrısı öncesi/sonrası RSS'i `psutil` ile ölçtüm — **0.1MB fark**, dosya boyutuyla orantılı DEĞİL. Bu, önceki incident'ın (149MB dosya → 969MB bellek) kök nedenini doğrudan hedefleyen ve bu implementasyonun gerçekten çözdüğünü kanıtlayan test.

## CAVEMAN / Definition of Done kontrolü
- Yeni soyutlama yok — mevcut `_approve_lock` paylaşıldı (yeni lock icat edilmedi).
- Migration script tek fonksiyonlu, basit hata yönetimi (dosya yok / hedef zaten var / format yanlış).
- `_atomic_write`'a dokunulmadı (başka yerlerde kullanılıyor).
- Kapsam dışı hiçbir şeye dokunulmadı (`_is_valid_city`, `_submission_queue`, response formatları, validasyon mantığı).
- Test dosyasına dokunulmadı.
- HİÇBİR YERDE (migration script HARİÇ, kasıtlı/dokümante edilmiş istisna) dosyanın tam içeriği `json.load()` ile okunmuyor.

## Sıradaki adım
`verify` — gerçek test/güvenlik gate'lerini çalıştıracak, AYRICA gerçek ölçekte bellek testinin (bu dosyada zaten yapıldı) tekrar teyit edilmesi önerilir.
