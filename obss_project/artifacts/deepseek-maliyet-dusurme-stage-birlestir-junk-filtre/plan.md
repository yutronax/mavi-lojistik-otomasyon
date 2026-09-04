# Plan — deepseek-maliyet-dusurme-stage-birlestir-junk-filtre
_Reference: atdd.md_

## Kararlar (atdd.md'nin Unknown'unu ÇÜRÜTEN kritik bulgu)

### atdd.md'nin varsayımı YANLIŞTI — Stage 1 çıktısı gerçekten kullanılıyor, salt "hint" değil
[text_gen_parser.py:352-357](text_gen_parser.py:352):
```python
# 2. Stage 1 (Ground Truth)
confirmed_locs = ""
if len(message) > 150:
    confirmed_locs = await self._extract_locations_stage1_async(message)
loc_guideline = f"\nCONFIRMED ROUTES (Priority):\n{confirmed_locs}\n" if confirmed_locs else ""
```
Stage 1'in döndürdüğü rota satırları **doğrudan Stage 2'nin promptuna**
`CONFIRMED ROUTES (Priority)` başlığıyla gömülüyor ([satır 378](text_gen_parser.py:378),
`{loc_guideline}`). Bu, atdd.md'nin "muhtemelen bağımsız kullanılmıyordu"
varsayımının **YANLIŞ** olduğunu kanıtlıyor — Stage 1 gerçek bir "ground
truth ön-geçiş" mekanizması, özellikle **150 karakterden uzun** (çoğu
gerçek ilan mesajı bu sınırı aşıyor) mesajlarda modelin çok-bölümlü/
karmaşık rotalarda (header reset, chaining önleme vb. — sistem promptunda
20+ kural var) yanlış çıkarım yapmasını önlemeye yönelik.

**Sonuç: Stage 1'i düz bir `Read`/silme ile kaldırmak DOĞRUDAN AC-1'i
karşılasa da AC-2'yi (regresyon: mevcut davranış korunmalı) RİSKE ATAR** —
uzun/karmaşık mesajlarda parse doğruluğu düşebilir.

### Revize edilmiş yaklaşım: Stage 1'i AYRI ÇAĞRI olarak değil, Stage 2'nin İÇİNDE bir akıl yürütme adımı olarak birleştir
Stage 2'nin JSON şeması zaten bir `akil_yurutme` alanı istiyor ([satır 452](text_gen_parser.py:452))
— model her yanıtta kısa bir analiz yazıyor ama bu şu an sadece dekoratif,
hiçbir yerde okunmuyor/kullanılmıyor (`_process_raw_json_async`'e sadece
`routes` gidiyor). Bu, Stage 1'in "önce rotaları belirle, sonra JSON'a
dök" mantığını **TEK bir çağrıda** tekrar üretmek için hazır bir kanca:
Stage 2'nin promptuna, mesaj 150 karakterden uzunsa, Stage 1'in system
promptundaki kuralları (header reset, chaining önleme, çoklu bölüm) da
içeren GÜÇLENDİRİLMİŞ bir "önce CONFIRMED ROUTES'u kendi içinde çıkar,
sonra JSON'a dök" talimatı eklenecek — `akil_yurutme` alanı bu ara adımı
taşıyacak. Ayrı bir API çağrısı yapılmayacak.

**Bu, düz silmeden daha az risklidir** ama YİNE DE bir davranış
değişikliği — doğruluk regresyonu riski sıfıra inmiyor, sadece azalıyor.
Bu yüzden **AC-2 (regresyon testi) bu görevde EN KRİTİK test** haline
geliyor: `test-copilot`, `data/onaylanmamis_ayristirilmis_log.json`'daki
150+ karakterlik GERÇEK çok-bölümlü mesajları alıp (mock'lu, aynı
LLM-çıktısı varsayımıyla) hem ESKİ iki-çağrı davranışını hem YENİ tek-
çağrı promptunu karşılaştırmalı test etmeli.

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| [text_gen_parser.py](text_gen_parser.py) | AC-1,2,6: `_extract_locations_stage1_async` çağrısı kaldırılacak, Stage 2 promptuna (satır 375-452) Stage 1'in "ground truth" kurallarını içeren güçlendirilmiş bir dahili akıl-yürütme talimatı eklenecek | **medium** (doğruluk regresyon riski, testle azaltılıyor) |
| [src/parsers/veri_cekici_ayristirici.py](src/parsers/veri_cekici_ayristirici.py) | AC-3,4,5: `add_to_processing_queue()`'ya (satır 446-510) yeni `_is_junk_message()` çağrısı eklenecek | low |

## New Files
| File | Purpose |
|------|---------|
| tests/test_stage_merge_call_count.py | AC-1,2,6: mock'lu testlerle mesaj başına DeepSeek+Groq çağrı sayısının ~2'den ~1'e düştüğünü VE mevcut retry/fallback/boş-routes davranışının değişmediğini doğrular |
| tests/test_junk_message_filter.py | AC-3,4,5: `_is_junk_message()`'ın gerçek geçmiş veri üzerinde (en az 20-30 örnek, `data/onaylanmamis_ayristirilmis_log.json`'dan) false-positive üretmediğini VE bariz junk'ı elediğini doğrular |

## Dependencies
- `_tag_cities()` ([text_gen_parser.py:165-193](text_gen_parser.py:165)) —
  junk filtresi bu fonksiyonun kullandığı şehir/hub/alias listesini
  (satır 175-179) TEKRAR KULLANACAK (import/erişim yolu `plan`'da
  netleşti: `TextGenParser` sınıfı içinde metod olarak tanımlı, junk
  filtresi `veri_cekici_ayristirici.py`'de OLACAĞI için bu listenin ya
  `text_gen_parser`'dan import edilmesi ya da ayrı bir sabit modüle
  taşınması gerekecek — code-copilot bu detayı çözecek, listenin
  KENDİSİ tekrar YAZILMAYACAK).
- `_extract_locations_stage1_async`'in system promptundaki kurallar
  ([satır 263-269](text_gen_parser.py:263)) — Stage 2'nin promptuna
  entegre edilecek referans metin.
- Mevcut retry+model-fallback zinciri ([satır 459-609](text_gen_parser.py:459)) —
  DOKUNULMUYOR, sadece "2 stage x kendi zincir" yerine "1 stage x aynı
  zincir" olacak.

## Migration Required?
Hayır — düz kod/prompt değişikliği, veri şeması değişmiyor.

## Risks
- **(atdd.md'den revize)** Stage 1'in ayrı çağrı olarak kaldırılıp tek
  promptta birleştirilmesi, 150+ karakterlik ÇOK-BÖLÜMLÜ mesajlarda
  (header reset, "---" ayraçları, chaining önleme) doğruluk regresyonuna
  yol açabilir — bu artık SADECE teorik bir risk değil, kod okumasıyla
  DOĞRULANMIŞ bir mimari gerçek. `test-copilot`'un AC-2 testi bunun
  ÖLÇÜLEBİLİR kanıtını üretmeli (gerçek çok-bölümlü mesaj örnekleriyle).
- Junk filtresinin `_tag_cities`'in şehir/hub listesini paylaşması için
  bir kod-organizasyon kararı gerekiyor (import döngüsü riski:
  `veri_cekici_ayristirici.py` zaten `text_gen_parser` içeren
  `production_parser`'ı import ediyor mu kontrol edilmeli — muhtemelen
  evet, `ProductionParser` üzerinden zaten erişim var).

## Open Questions
Yok — atdd.md'nin tek büyük Unknown'u (Stage 1 çıktısının kullanılıp
kullanılmadığı) kod okumasıyla KESİN olarak çözüldü (kullanılıyor).
Kalan tek belirsizlik (junk filtresinin import yolu) code-copilot
seviyesinde çözülebilecek kadar küçük, sub-agent dispatch'ine gerek yok.
