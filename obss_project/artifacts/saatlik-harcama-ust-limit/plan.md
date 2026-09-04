# Plan — saatlik-harcama-ust-limit
_Reference: atdd.md_

## Kararlar (atdd.md'nin Unknown'unu çözen kod bulgusu)

### Ertelenmiş mesajlar için AYRI bir veri yapısı GEREKMİYOR — mevcut örüntü zaten bunu çözüyor
[veri_cekici_ayristirici.py:598-607](src/parsers/veri_cekici_ayristirici.py:598) —
mevcut kod, bir mesaj o an aktif olarak işleniyorsa (`active_ids`/
`active_body_hashes`) sadece `continue` ile atlıyor, `mark_id_handled`
ÇAĞIRMIYOR. Bu, mesajın bir sonraki fetch/webhook döngüsünde DOĞAL olarak
tekrar geleceği ve o zaman işleneceği anlamına geliyor (sistem zaten bu
"şimdi değil, sonra tekrar dene" örüntüsünü kullanıyor).

**Sonuç: saat başı limit aşıldığında da AYNI örüntüyü kullanabiliriz** —
mesajı kuyruğa EKLEMEDEN, `mark_id_handled` ÇAĞIRMADAN `continue` ile
atla. Kaynak (Baileys webhook / Whapi poll) bu mesajı zaten-işlenmiş
listesine hiç girmediği için bir sonraki fetch döngüsünde TEKRAR
sunacak — o zaman saat değişmişse (veya limit altına düşmüşse) normal
işlenecek. **Bu, atdd.md'nin Unknown'unda sorulan "ayrı bir erteleme
yapısı mı" sorusunu çözüyor: HAYIR, mevcut "aktif/duplicate skip"
örüntüsü zaten yeterli, yeni bir dosya/liste icat ETMİYORUZ** (CAVEMAN).

### Bellek-içi sayaç: modül seviyesinde, `text_gen_parser.py` içinde
[text_gen_parser.py:107-146](text_gen_parser.py:107) — `_track_spend()`
zaten `cost_try` hesaplıyor (satır 122). Bu fonksiyonun HEMEN
YANINA, modül seviyesinde (sınıf dışı, çünkü `veri_cekici_ayristirici.py`
bu değere `add_to_processing_queue()`'dan erişecek ve `TextGenParser`
instance'ına her zaman erişimi olmayabilir — modül-seviyesi fonksiyon
daha basit bir kontrat) şu eklenecek:
```python
_hourly_lock = threading.Lock()
_current_hour_key = None
_current_hour_cost_try = 0.0

def is_hourly_cap_exceeded() -> bool:
    cap = float(os.getenv('AI_HOURLY_SPEND_CAP_TRY', '9'))
    with _hourly_lock:
        return _current_hour_cost_try > cap  # AC-6: > değil >=... yani > kullan
```
`_track_spend()`'in `if cost > 0:` bloğunun İÇİNDE, `cost_try`
hesaplandıktan hemen sonra, saat anahtarı (`datetime.now().strftime('%Y-%m-%d-%H')`)
değiştiyse sayaç sıfırlanıp yeni saate geçilecek (AC-4), değişmediyse
`_current_hour_cost_try`'a eklenecek — hepsi `_hourly_lock` altında
(thread-safety, atdd.md'nin Risk'inde belirtildiği gibi 50 worker aynı
anda güncelleyebilir).

### Restart-kurtarma: AC-5'in fail-open ilkesiyle TUTARLI, basit bir çözümle
Uygulama yeniden başladığında `_current_hour_cost_try` sıfırdan başlar —
atdd.md'nin Risk'i bunu "kısa süreliğine limitsiz kalma" olarak kabul
edilebilir görmüştü. `plan` aşamasında EK bir çözüm bulundu (basit,
CAVEMAN): modül import edildiğinde (ilk çağrıda, `_current_hour_key is
None` iken) `ai_spend_history.json`'u BİR KEZ okuyup mevcut saatin
kayıtlarını toplayıp `_current_hour_cost_try`'ı bu değerle ilklendirmek
— bu, atdd.md'nin önerdiği "process başlangıcında bir kez oku"
performans hedefiyle birebir uyumlu, AYRI bir mekanizma DEĞİL, sadece
`is_hourly_cap_exceeded()`'in ilk çağrısında lazy-init.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| [text_gen_parser.py](text_gen_parser.py:107) | AC-2,4,5,6: modül seviyesinde sayaç + `is_hourly_cap_exceeded()` fonksiyonu, `_track_spend()`'e güncelleme çağrısı | low |
| [src/parsers/veri_cekici_ayristirici.py](src/parsers/veri_cekici_ayristirici.py:613) | AC-1,2,3: `add_to_processing_queue()`'da junk-filtre kontrolünden HEMEN SONRA (satır ~626, `processing_queue.put`'tan önce) limit kontrolü eklenecek | low |

## New Files
| File | Purpose |
|------|---------|
| tests/test_hourly_spend_cap.py | AC-1,2,3,4,5,6: eşik altı/üstü/tam sınır, saat geçişi, bozuk veri fail-open, restart-kurtarma lazy-init senaryolarını test eder |

## Dependencies
- `_track_spend()` ([text_gen_parser.py:107](text_gen_parser.py:107)) —
  yeni sayaç güncellemesi bu fonksiyonun İÇİNE eklenecek, mevcut davranışı
  (dosyaya yazma, log) DEĞİŞTİRMEYECEK.
- `add_to_processing_queue()`'daki mevcut "aktif/duplicate skip" örüntüsü
  ([satır 598-607](src/parsers/veri_cekici_ayristirici.py:598)) — yeni
  limit kontrolü bu örüntüyü TAKLİT EDECEK (yeni bir yapı icat etmeden).
- `os.getenv('AI_HOURLY_SPEND_CAP_TRY', '9')` — yeni env değişkeni,
  `.env.example`'a da eklenmeli (kullanıcı isterse).

## Migration Required?
Hayır — düz kod değişikliği + yeni bir env değişkeni (varsayılan değerle
mevcut davranışı bozmaz).

## Risks
- (atdd.md'den korunan) Thread-safety: `_hourly_lock` ile çözüldü,
  `plan`'da somut kod tasarımı netleşti.
- (atdd.md'den korunan, KISMEN çözüldü) Restart-sonrası sayaç sıfırlanması:
  lazy-init ile `ai_spend_history.json`'dan o saatin gerçek toplamı
  kurtarılacak — TAMAMEN çözülmüş sayılmaz çünkü dosya kendisi de
  bozuksa (AC-5) fail-open'a düşülüyor (sayaç 0'dan başlıyor, kısa
  süreliğine limitsiz) — bu KABUL EDİLEBİLİR bir risk (atdd.md'nin
  kendi kararı).
- `AI_HOURLY_SPEND_CAP_TRY` varsayılanı (9 TL/saat) kullanıcı tarafından
  HENÜZ KESİN onaylanmadı (atdd.md'de "öneri" olarak işaretli) — `code-
  copilot`'a geçmeden önce kullanıcıya bu sayı teyit ettirilmeli.

## Open Questions
Yok — atdd.md'nin tek büyük Unknown'u (erteleme yapısı) kod
incelemesiyle kesin çözüldü (mevcut örüntü yeterli, yeni yapı gerekmiyor).
Eşik değeri (9 TL/saat) bir ONAY sorusu, açık bir TEKNİK soru değil —
kullanıcıya ATDD onayı sırasında zaten soruldu, `code-copilot` bu
varsayılanla ilerleyebilir (kullanıcı env değişkeniyle sonradan
değiştirebilir).
