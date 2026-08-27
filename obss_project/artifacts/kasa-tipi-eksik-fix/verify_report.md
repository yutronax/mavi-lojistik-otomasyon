# Verify Report — kasa-tipi-eksik-fix
_Reference: atdd.md, code_diff.md, test_diff.md_

## Verification Gates
| # | Gate | Result | Evidence / Reason |
|---|------|--------|--------------------|
| 1 | Dosya konumu | PASS | `git status --short` → `M src/utils/vehicle_type_matcher.py`, `M text_gen_parser.py`, `?? tests/test_kasa_tipi_eksik_fix.py` — hepsi `Read` ile teyit edildi. |
| 2 | Build/derleme | PASS | Projenin CI'ı (`.github/workflows/ci.yml`) ayrı bir build adımı içermiyor, doğrudan `pytest -q` çalıştırıyor (gate 6). `ast.parse` ile sözdizimi ayrıca doğrulandı, hata yok. |
| 3 | Supabase şema/canlı doğrulama | N/A | Proje Supabase kullanmıyor, değişen dosyalar Supabase çağrısı/migration içermiyor. |
| 4 | Lint | N/A | Repo'da linter/formatter konfigürasyonu yok (bkz. önceki görevde de doğrulandı), CI de çalıştırmıyor. |
| 5 | Type check | N/A | Repo'da type-checker konfigürasyonu yok. |
| 6 | Unit testler | PASS | Projenin gerçek CI komutu: `python -m pytest -q` (proje kökünden) → **18 passed in ~18-19s**, bağımsız olarak birden fazla kez tekrarlandı, tutarlı. |
| 7 | E2E testler | N/A | Bu görevde e2e altyapısı yok. |
| 8 | Lighthouse (performans) | N/A | Web UI değişikliği yok (backend kural-eşleştirme mantığı). |
| 9 | Erişilebilirlik | N/A | Aynı sebep. |
| 10 | Güvenlik taraması | PASS (1 tur düzeltmeyle) | İlk tarama `hashlib.md5()`'i zayıf hash kullanımı (B324, HIGH) olarak işaretledi — bu MD5 kullanımı güvenlik amaçlı değil (sadece log kaydı için mesaj özeti), `usedforsecurity=False` eklenerek düzeltildi. Düzeltme sonrası tarama: `{"secrets": PASS, "python_sast": PASS, "python_deps": PASS}` → **verdict: PASS**. |
| 11 | AI code review | PASS (2 tur, HIGH+MEDIUM bulundu, HIGH düzeltildi) | `obss-red-team` çalıştırıldı: 1 HIGH (yanlış-pozitif flag, "kapalı açık farketmez" gibi meşru eşleşmeler) düzeltildi ve bağımsız doğrulandı; 1 MEDIUM (log dosyası yarış durumu) kabul edilmiş, kullanıcıya bildirilecek sınırlama olarak bırakıldı (detay: bu dosyanın "Red-team turu" bölümü). |
| 12 | Görsel regresyon | N/A | Web UI kapsamda değil. |
| 13 | İnsan onayı | PENDING | Kullanıcı onayı bekleniyor. |

## AC → Test Mapping
1. [Critical] Happy path, regresyon yok → `TestHappyPathRuleMatch::test_rule_match_happy_path_no_uncertainty_flag` → PASS
2. [Critical] İpucu yok → flag + sebep → `TestNoHintUncertainty::test_no_hint_sets_uncertainty_ipucu_yok` → PASS
3. [Critical] İpucu var, kural eşleşmedi → flag + sebep + log → `TestHintButNoRuleMatch::test_hint_but_no_match_writes_unmatched_log` → PASS
4. [High] Çok rotalı bağımsız değerlendirme → `TestMultiRouteIndependentEvaluation::test_multi_route_independent_flags` → PASS
Yardımcı: `TestVehicleTypeMatcherKeywordExtraction::*` (3 test), `TestEdgeCases::*` (2 test) → PASS

## Coverage / Quality Notes
- atdd.md'nin 4 AC'sinin tümü en az bir testle kaplanmış.
- Test-copilot adımında ilk yazımda 2 test (AC-3'ün dosya-yazma kontrolü, AC-4'ün rota-bağımsızlığı) gerçek assertion içermiyordu — düzeltilip bağımsız doğrulandı (bkz. test_diff.md).
- Code-copilot adımında implementasyonda 2 gerçek sorun bulunup düzeltildi: (1) log kaydındaki `msg_id` sahte/anlamsızdı (`route_idx` yerine artık mesaj içeriğinden türetilen `msg_hash` kullanılıyor), (2) `global_type_match` ölü kod olarak kalmıştı, temizlendi.
- **Bilinen, kabul edilmiş sınırlama** (code_diff.md'de not edildi, atdd.md'nin Assumptions'ında zaten öngörülmüştü): `known_kasa_keywords` seti sadece kasa-tipi değil, `yuk_tipi.json`'daki TÜM kural pattern'lerinden (araç tipi, yük tipi dahil) türetiliyor — bu, "ipucu_yok" ile "kural_eslesmedi" ayrımının bazı durumlarda beklenenden az hassas olmasına yol açabilir (flag'in kendisi yine de doğru "belirsiz" oluyor, sadece sebep etiketi bazen yanlış kategoriye düşebilir). Kullanıcı onayına sunulacak.

## Red-team sonrası düzeltme turu (2. tur)
İlk red-team taraması 2 HIGH bulgu tespit etti:
1. **Race condition**: `data/eslesmeyen_kasa_ifadeleri.json`'a yazım `save_json_safe` (kilit yok) ile yapılıyordu, projenin standart eşzamanlı-yazım deseni olan `persistence_manager.queue_write()` yerine. **Düzeltildi.**
2. **`route_context`'ten `type` alanının kaybı**: İlk implementasyon `route_context`'i sadece `found_line`/`n_il+ny_il`'den oluşturuyordu, AI'nin çıkardığı `r.get('type', '')` ipucunu atlıyordu — bu, önceden çalışan araç/yük-tipi eşleştirmesinde regresyona yol açabilirdi. **Düzeltildi**: `route_context`'e `type` geri eklendi.

Bu 2. düzeltme sonrasında, düzeltme #2'nin YENİ bir etkileşim hatası yarattığı bağımsız doğrulamayla tespit edildi: AI'nin ürettiği `type` değeri (ör. "1360" gibi bare bir tonaj kodu) `find_match()`'te GENEL bir kurala eşleşiyor ve bu kural bizim "eşleşme yok" varsayılanıyla (`AÇIK+KAPALI`) BİREBİR AYNI `KASA TİPİ` değerini üretiyordu — kod bunu "güvenilir eşleşme" sayıp AC-2/AC-3'ün belirsizlik mantığını tamamen atlıyordu. Doğrudan Python reprodüksiyonuyla doğrulandı (`VehicleTypeMatcher.find_match('ANKARA İSTANBUL 1360', per_route=True)` → generic `AÇIK+KAPALI` sonuç döndürüyor, `has_kasa_hint` de "1360" token'ı yüzünden yanlışlıkla True dönüyordu).

**3. tur düzeltme (uygulandı ve bağımsız doğrulandı):**
- `has_hint`, artık `route_context` (type dahil) yerine ayrı bir `hint_context`'ten (sadece gerçek mesaj metni — `found_line`/`n_il+ny_il`, `type` HARİÇ) hesaplanıyor. Bu, AI'nin neredeyse her rotaya koyduğu genel `type` değerinin "ipucu var" sayılmasını (ve `"ipucu_yok"` durumunu neredeyse erişilemez kılmasını) önlüyor.
- Belirsizlik değerlendirmesi artık `type_match` var/yok koşuluna değil, üretilen `kasa_tipi` kümesinin genel varsayılanla (`{AÇIK, KAPALI}`, case-insensitive) AYNI olup olmadığına (`is_generic_kasa`) bağlı — eşleşme "gerçek" (spesifik, ör. FRİGO/DAMPERLİ) olduğunda flag atlanıyor, sadece genel varsayılana denk düştüğünde belirsizlik değerlendirmesi çalışıyor.
- `route_context`'e `type` eklenmesi (düzeltme #2, eşleştirme kalitesi için) korunuyor — sadece `has_hint` hesaplaması ondan ayrıştırıldı.

**Bağımsız doğrulama (bu turda tekrar çalıştırıldı):**
```
python -m pytest tests/test_kasa_tipi_eksik_fix.py tests/test_deepseek_cost_fix.py -v --tb=short
18 passed in 21.39s
```
`ast.parse` ile sözdizimi doğrulandı. `_track_spend()`'in `ai_spend_history.json` yazımı (satır 141, `save_json_safe`) hâlâ yerinde ve dokunulmamış — kapsam dışı sapma yok. Güvenlik taraması tekrar çalıştırıldı: `{"secrets": PASS, "python_sast": PASS, "python_deps": PASS}` → **verdict: PASS**.

## 2. Red-team turu (obss-red-team subagent) ve 4. düzeltme
3. turdaki `is_generic_kasa` (çıktı değerini `{AÇIK, KAPALI}` sabit kümesiyle karşılaştırma) yaklaşımı `obss-red-team` tarafından incelendi ve **1 HIGH + 1 MEDIUM** bulgu raporlandı:

- **HIGH (doğrudan reprodüksiyonla doğrulandı):** `is_generic_kasa` mantığı, çıktısı MEŞRU şekilde `AÇIK + KAPALI` olan gerçek kuralları (ör. müşterinin açıkça yazdığı "kapalı açık farketmez" ifadesi, kural tablosunda yüksek öncelikli, kasıtlı bir kural) yanlışlıkla "belirsiz, kural_eslesmedi" olarak işaretliyordu — AC-1'in "gerçek eşleşmede regresyon yok" garantisini ihlal ediyordu. Doğrudan test edilerek doğrulandı: `find_match('ANKARA İSTANBUL kapalı açık farketmez')` → `{'KASA TİPİ': 'AÇIK + KAPALI', ...}` (doğru cevap) ama flag yanlışlıkla tetikleniyordu.
- **MEDIUM:** `data/eslesmeyen_kasa_ifadeleri.json`'a yazım deseni (`load_json_safe` → append → `persistence_manager.queue_write`) atomik değil — `persistence_manager.py` okundu ve doğrulandı: `queue_write` sadece kuyruğa alınan tam listeyi olduğu gibi yazıyor, flush anında dosyayı tekrar okumuyor. Eşzamanlı mesaj işleme (`asyncio.gather`) altında iki rota/mesaj aynı eski dosya içeriğini okuyup ayrı ayrı kuyruğa alırsa, sonraki yazım öncekini sessizce eziyor — bazı log kayıtları kaybolabilir.

**4. düzeltme (HIGH bulgu için, uygulandı ve bağımsız doğrulandı):** `is_generic_kasa` mantığı tamamen kaldırıldı. Belirsizlik artık SADECE `has_hint` (gerçek mesaj metninde ipucu var mı) ve `type_match`'in var/yok olmasına (çıktı DEĞERİNE bakmadan) göre değerlendiriliyor:
- `has_hint` False → `"ipucu_yok"`.
- `has_hint` True ve `type_match` yok → `"kural_eslesmedi"` + log.
- `has_hint` True ve `type_match` var → flag YOK (matcher'ın gerçek ipuçlarını çıktıya doğru yansıttığı ayrıca doğrulandı: `FRİGO` içeren mesaj → `FRİGO + KAPALI` dönüyor, ipucu kaybolmuyor).

Bağımsız doğrulama (bu turda tekrar):
```
python -m pytest tests/test_kasa_tipi_eksik_fix.py tests/test_deepseek_cost_fix.py -v --tb=short
18 passed in 23.02s
```
```python
find_match('ANKARA İSTANBUL kapalı açık farketmez')  # -> AÇIK+KAPALI, has_hint=True, type_match var -> flag YOK (düzeltildi)
has_kasa_hint('ANKARA İSTANBUL')  # -> False (type hariç) -> "ipucu_yok" (korunuyor)
```
`ast.parse` ile sözdizimi doğrulandı.

**MEDIUM bulgu (race condition) — kabul edilmiş, kullanıcıya bildirilecek sınırlama:** Bu, sadece aynı log dosyasına aynı anda yazan birden fazla eşzamanlı mesaj/rota olduğunda ortaya çıkan, düşük olasılıklı bir yarış durumu. Düzgün çözümü `persistence_manager.py`'nin genel `queue_write` sözleşmesini (worker-side atomik "oku+ekle+yaz" birincil işlemi eklemek üzere) değiştirmeyi gerektirir — bu, projenin paylaşılan, birden fazla çağrı noktası tarafından kullanılan bir servisini etkileyen, bu görevin CAVEMAN kapsamının çok üzerinde bir mimari değişiklik. Etkilenen veri (`eslesmeyen_kasa_ifadeleri.json`) iş-kritik değil, sadece ileride kural tablosunu geliştirmek için biriktirilen tanılama/log verisi — kayıp olsa bile üretim akışını veya YukBurada'ya giden veriyi etkilemiyor. Kullanıcı onayına sunulacak, düzeltilmeden commit'e devam edilmesi öneriliyor.
