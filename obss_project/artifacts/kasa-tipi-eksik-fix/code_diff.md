# Code Diff — kasa-tipi-eksik-fix
_Reference: plan.md, test_diff.md_

## Değiştirilen Dosyalar
- `src/utils/vehicle_type_matcher.py`
- `text_gen_parser.py`

## AC → Uygulama eşleşmesi
| AC | Nasıl karşılandı |
|---|---|
| AC-1 (regresyon yok) | Kural eşleştiğinde davranış değişmedi (`type_match` bulunursa eski kod aynen çalışır, flag eklenmez). |
| AC-2 (ipucu yok → flag) | `VehicleTypeMatcher.__init__`'te `data/yuk_tipi.json`'daki tüm pattern kelimelerinden `self.known_kasa_keywords` seti bir kez çıkarılıp cache'leniyor; yeni `has_kasa_hint()` metodu bunu kullanıyor. Eşleşme yoksa ve `has_kasa_hint()` False ise `kasa_tipi_belirsiz_sebep = "ipucu_yok"`. |
| AC-3 (ipucu var, eşleşmedi → flag+log) | `has_kasa_hint()` True ama kural eşleşmediyse `kasa_tipi_belirsiz_sebep = "kural_eslesmedi"`, `data/eslesmeyen_kasa_ifadeleri.json`'a mevcut `load_json_safe`/`save_json_safe` yardımcılarıyla kayıt eklenir. |
| AC-4 (çok rotalı bağımsız değerlendirme) | Her rota kendi `route_context`'i üzerinden bağımsız değerlendiriliyor; global fallback (`global_type_match`) kasıtlı olarak kaldırıldı. |

## Review sırasında bulunan ve düzeltilen 2 gerçek sorun (ilk implementasyonda vardı, plan.md'de öngörülmemişti)
1. **Sahte `msg_id`:** İlk halde log kaydı `"msg_id": f"route_{route_idx}"` kullanıyordu — bu sadece o çağrıdaki rota sırasıydı (0,1,2...), her mesajda sıfırdan başladığı için GERÇEK bir mesaj kimliği değildi, log kayıtları birbirinden ayırt edilemiyordu. Düzeltme: `message` parametresinden `hashlib.md5(...)` ile türetilen 12 karakterlik bir hash (`msg_hash`) kullanılıyor — aynı mesajdan gelen rotalar aynı kimliği paylaşıyor, farklı mesajlar farklı kimlik alıyor. Fonksiyon imzaları değiştirilmedi (kapsam korundu, `parse_async`/`_process_raw_json_async`'e yeni parametre eklenmedi).
2. **Ölü kod:** `global_type_match = self.vehicle_matcher.find_match(message, per_route=False)` satırı hesaplanıyor ama hiç kullanılmıyordu (AC-4 gereği fallback kaldırılmıştı, ama hesaplama unutulmuştu) — gereksiz bir API çağrısıydı. Tamamen silindi.

## Test Sonucu (bağımsız doğrulandı)
```
python -m pytest tests/test_kasa_tipi_eksik_fix.py tests/test_deepseek_cost_fix.py -v
18 passed in ~17s
```
(Önceki görevin — deepseek-cost-fix — testleri de dahil edilerek regresyon kontrolü yapıldı, hepsi geçiyor.)

## CAVEMAN / Definition of Done kontrolü
- Yeni dosya yok (kod tarafında — `data/eslesmeyen_kasa_ifadeleri.json` çalışma zamanında oluşacak bir veri dosyası, kod dosyası değil).
- Yeni soyutlama: `has_kasa_hint()` — gerekçesi: AC-3'ün gerektirdiği "ipucu var mı" bilgisi `VehicleTypeMatcher`'ın zaten sahip olduğu kural verisine bağımlı, doğal olarak o sınıfa ait.
- `find_all_matches`/`find_match`'in mevcut dönüş tipi/imzası DEĞİŞMEDİ.
- Panel UI'a dokunulmadı (plan.md kararına uygun).
- Kapsam dışı hiçbir şeye dokunulmadı.

## Bilinen sınırlama (red-team'e taşınacak, bu görevi bloklamıyor)
`known_kasa_keywords` seti, `yuk_tipi.json`'daki TÜM kural pattern'lerinden (sadece KASA TİPİ değil, ARAÇ TİPİ ve YÜKÜN TİPİ kurallarını da içeren pattern metinlerinden) türetiliyor — yani "TIR", "1360" gibi araç-tipi kelimeleri de bu sete dahil olabilir. Bu, "kasa tipi ipucu" tespitinin bazen aslında sadece araç/tonaj bilgisi içeren mesajları da "ipucu var" (dolayısıyla "kural_eslesmedi") olarak işaretlemesine yol açabilir — AC-2 ile AC-3 arasındaki ayrımın hassasiyetini biraz düşürebilir. Fonksiyonel olarak yanlış değil (flag yine de doğru şekilde "belirsiz" olarak işaretliyor), ama `kasa_tipi_belirsiz_sebep` değeri bazı durumlarda "ipucu_yok" yerine "kural_eslesmedi" çıkabilir. Bu, atdd.md'nin Assumptions bölümünde zaten "kesin algoritma netleşmedi" olarak işaretlenmişti — kabul edilebilir bir sınırlama.

## Sıradaki adım
`verify` — gerçek test/güvenlik gate'lerini çalıştıracak.
