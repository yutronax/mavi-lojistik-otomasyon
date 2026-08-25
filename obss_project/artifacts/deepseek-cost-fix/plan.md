# Plan — deepseek-cost-fix
_Reference: atdd.md_

## Files to Modify

| File | Why | Risk |
|------|-----|------|
| `text_gen_parser.py` | Model sabitleri (`self.model_gemini`, `self.model_fast`, `self.model_robust`, `self.fallback_models`) yeniden düzenlenecek: Groq modeli birincil, DeepSeek modelleri fallback listesine taşınacak (AC-1). | medium |
| `text_gen_parser.py` — `_extract_locations_stage1_async()` (satır ~241-309) | **Gerçek bug bulundu:** `else` dalı (satır 285-294, Groq/"diğer" yolu) API çağrısını `model=self.model_fast` ile yapıyor, döngüdeki `model_to_use` değişkeniyle DEĞİL. `self.model_fast` şu an `'deepseek-v4-flash'`. Yani `self.model_gemini`'yi bir Groq model adına çevirsek bile, bu satır hâlâ sabit olarak DeepSeek'i çağırır — Stage 1 asla gerçekten Groq'a gitmez. Bu satır `model=model_to_use` ve `self._track_spend(model_to_use, ...)` olarak düzeltilmeli. Ayrıca Stage 1'in kendisi şu an TEK model deniyor (retry sadece aynı modelde 429 durumunda) — AC-2 gereği Stage 1'in de Groq başarısız olunca DeepSeek'e düşmesi gerekiyor, bu da fonksiyonun Stage 2'deki gibi bir `models_to_try` listesi üzerinde döngü kurmasını gerektirir (yapısal değişiklik, tek satır düzeltme değil). | high |
| `text_gen_parser.py` — `parse_async()` ana döngüsü (satır ~439-479) | AC-3 gereği: bir model API çağrısı BAŞARIYLA dönse bile ürettiği `routes` boşsa (kalite yetersiz/"karmaşık mesaj" — quality-gate'in reddettiği durumun ön-hali), döngü bu sonucu hemen `return` ETMEMELİ, `models_to_try` listesinde son model değilse bir sonraki modele (DeepSeek) geçmeli. Şu anki kod her başarılı API yanıtında (boş olsa bile) hemen dönüyor — bu davranış AC-3'ü karşılamıyor, değiştirilmesi gerekiyor. | high |
| `text_gen_parser.py` — `_track_spend()` (satır ~104-134) | AC-6 gereği: `ai_spend_history.json`'a yazılan her kayda `provider` alanı eklenmeli (`"groq"` / `"deepseek"` / mevcut model adından türetilir). Fiyatlandırma sabitleri de gerekirse Groq için eklenmeli — mevcut kod zaten `elif "llama" in model_name` gibi bir dal içeriyor (Groq'un eski fallback modelleri için), bu dalın fiyatı GÜNCEL Groq tarifesiyle ($0.05/$0.08 per 1M, Llama 3.1 8B Instant) doğrulanmalı/güncellenmeli. | medium |
| `src/api/admin_panel.py` | `ai_spend_history.json` panelde "AI COST" olarak okunuyorsa (bu görev başında referans verildi), yeni `provider` alanının panel tarafında kırılmaya (KeyError vb.) yol açmadığından emin olunmalı — muhtemelen sadece okuma tarafı, `.get('provider', 'deepseek')` gibi geriye dönük uyumlu bir varsayılanla. | low |
| `.env` (VPS'te, bu repoda DEĞİL) | Yeni ve GEÇERLİ bir `GROQ_API_KEY`/`GROQ_API_KEYS` girilmeli — bu repodaki `.env` sadece yerel/placeholder (`gsk_test_placeholder`), gerçek anahtar VPS'in kendi `.env`'ine elle eklenmeli. Kod değişikliği DEĞİL, bir deploy ön-koşulu. | low |

## New Files
Yok — mevcut dosyalardaki değişiklikler yeterli, yeni bir modül/dosya gerekmiyor.

## Dependencies
- `src/utils/api_key_manager.py` (`APIKeyManager`) — Groq key rotasyonu (`GROQ_API_KEYS`/`GROQ_API_KEY` parse, `switch_to_next_async(key_type='groq', ...)`) **zaten tam çalışır durumda**, bu görevde değişiklik gerekmiyor. Yeni bir gerçek Groq anahtarı `.env`'e eklendiğinde otomatik olarak kullanılacak.
- `text_gen_parser.py` içindeki `_get_async_client()` (Groq/AsyncGroq client) **zaten mevcut ve doğru çalışıyor** — Stage 2'nin `else` dalı (satır 466-475) doğru şekilde `model=model_name` kullanıyor, değişiklik gerekmiyor.
- `src/utils/quality_gate.py` (`QualityGate.evaluate`) — AC-3'ün "kalite yetersiz" tespitinde tam `evaluate()` çağrısı KULLANILMIYOR (o, orchestrator'daki post-filter shipment listesine ihtiyaç duyuyor, `parse_async` bu bağlama sahip değil). Bunun yerine basit bir "boş `routes` listesi = yetersiz" kontrolü öneriliyor (bkz. Open Questions — bu bir tasarım kararı, onay gerekiyor).
- `production_parser.py` (root) — `ProductionParser.parse_message()` → `TextGenParser.parse()` (sync wrapper) → `asyncio.run(parse_async(...))` zincirini değiştirmiyoruz; tüm fallback mantığı `parse_async()` içinde kalıyor, üst katmanlara (orchestrator, `ProductionParser`) sızmıyor — bu, mevcut senkron/thread-pool mimariyle uyumlu kalmasını sağlıyor.

## Migration Required?
Hayır. `ai_spend_history.json`'a yeni bir `provider` alanı eklemek şema göçü değil, sadece yeni yazılan kayıtlara bir alan eklemek (eski kayıtlar `provider` alanı olmadan kalır, okuma tarafı `.get('provider', 'deepseek')` ile geriye dönük uyumlu olmalı — eski kayıtların hepsi zaten DeepSeek'ti).

## Risks
_(atdd.md'den taşındı + kod keşfinde netleşenler)_
- **Stage 1'deki gerçek bug** (yukarıda "Files to Modify" tablosunda detaylandırıldı) atdd.md'de öngörülmemişti — bu, sadece model adı/config değişikliği değil, gerçek bir mantık düzeltmesi ve yapısal değişiklik gerektiriyor (Stage 1'e de bir `models_to_try` döngüsü eklenmesi). Bu, görevin tahmin edilenden biraz daha büyük bir kod değişikliği olduğu anlamına geliyor.
- Groq'un Llama 3.1 8B modelinin Türkçe lojistik metin ayrıştırma doğruluğu test edilmedi (atdd.md Risks'te zaten belirtilmişti) — code-copilot adımında gerçek/örnek mesajlarla manuel doğrulama önerilir.
- İki adet `production_parser.py` (`./production_parser.py` ve `src/parsers/production_parser.py`) mevcut, sadece kök dizindeki import ediliyor (satır 62: `from production_parser import ProductionParser`). `src/parsers/production_parser.py` şu an KULLANILMIYOR (dead code) — bu görevin kapsamı dışında ama ayrı bir temizlik fırsatı olarak not edildi, bu plana dahil değil.
- Groq'un ücretsiz/ücretli kota (RPM/RPD) limitleri doğrulanmadı — code-copilot adımında console.groq.com üzerinden kontrol edilmeli, aksi halde 5000 mesaj/gün hacminde beklenmedik 429'lar (ve dolayısıyla beklenenden daha sık DeepSeek fallback'i, maliyeti geri yükseltebilir) oluşabilir.

## Open Questions
1. **Hangi Groq modeli?** atdd.md'nin Unknowns'ında bırakılmıştı. `llama-3.1-8b-instant` en ucuz ($0.05/$0.08) ama en küçük/muhtemelen en az doğru; `llama-3.3-70b-versatile` daha pahalı ama muhtemelen daha doğru. (Not: önceki oturumda `llama-3.3-70b-versatile` denendiğinde `404 model does not exist` hatası alınmıştı — bu model artık Groq'ta mevcut olmayabilir, code-copilot adımında `console.groq.com`'daki güncel model listesinden teyit edilmeli.)
2. **AC-3'ün ("kalite yetersiz mesajlarda DeepSeek'e düş") tam kontrol mantığı ne olmalı?** Bu planda basit bir kural öneriliyor: Groq'tan gelen `routes` listesi boşsa (parse başarılı ama 0 rota), bunu "yetersiz" sayıp DeepSeek'i dene. Alternatif: tam `QualityGate.evaluate()`'i `parse_async` içine taşımak (daha doğru ama daha invaziv, `evaluate()`'in orchestrator'daki post-filter mantığına bağımlılığı çözülmeli). **Onay gerekiyor: basit "boş routes" kuralı yeterli mi, yoksa tam quality-gate entegrasyonu mu isteniyor?**
3. Groq key'i `.env`'e ne zaman eklenecek — code-copilot çalışmadan ÖNCE mi (gerçek key ile test edilebilir), yoksa placeholder ile kod yazılıp sonra mı VPS'e gerçek key eklenecek? Gerçek key olmadan Groq entegrasyonu unit-test/mock ile doğrulanabilir ama gerçek doğruluk testi yapılamaz.

## Kararlar
1. **Model: `llama-3.1-8b-instant`** (Haiku alt-ajanı tarafından yanıtlandı: bütçe kritik, sistem zaten DeepSeek fallback'ine sahip olduğu için "yeterince iyi" küçük model yeterli; `llama-3.3-70b-versatile` önceki oturumda 404 vermişti — code-copilot, Groq'un güncel model listesini `console.groq.com`/API'den teyit etmeli, yazılı olarak varsayılmamalı).
2. **AC-3 kontrolü: Seçenek A — boş `routes` listesi = yetersiz, DeepSeek'e düş** (Haiku alt-ajanı tarafından yanıtlandı: mevcut `models_to_try` döngüsüne doğal oturuyor, `QualityGate.evaluate()`'i `parse_async`'e taşımak invaziv ve `evaluate()`'in orchestrator-bağımlı context'i olmadan doğru çalışmıyor).
3. **Groq key zamanlaması: Önce placeholder/mock ile kod yaz, key'i SONRA VPS'e ekle** (Haiku alt-ajanı tarafından yanıtlandı: kullanıcı henüz console.groq.com'dan yeni bir key almadı; unit/integration testler mock ile yapılabilir, gerçek doğruluk testi deploy sırasında VPS'te yapılır).
