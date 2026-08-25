# Code Diff — deepseek-cost-fix
_Reference: plan.md, test_diff.md_

## Değiştirilen Dosya
`text_gen_parser.py` (tek dosya, plan.md'nin öngördüğü gibi; ayrı bir orchestrator/panel değişikliği gerekmedi çünkü tüm fallback mantığı `parse_async`/`_extract_locations_stage1_async` içinde kaldı)

## AC → Uygulama eşleşmesi
| AC | Nasıl karşılandı |
|---|---|
| AC-1 (Groq önce) | `_get_model_for_message()` artık `'llama-3.1-8b-instant'` döner; Stage 2'nin `models_to_try = ['llama-3.1-8b-instant', self.model_robust] + self.fallback_models`; Stage 1'in kendi `models_to_try = ['llama-3.1-8b-instant', 'deepseek-v4-flash']` listesi eklendi. |
| AC-2 (Groq hata → DeepSeek) | Mevcut `for model_name in models_to_try` döngüsü + exception handling zaten bir sonraki modele geçiyordu; Stage 1'e de aynı döngü yapısı eklendi (önceden Stage 1 tek modeldi). |
| AC-3 (boş sonuç → DeepSeek retry) | Stage 2'de: başarılı yanıt sonrası `routes` boşsa VE son model değilse, `_process_raw_json_async`'e gitmeden `break` ile bir sonraki modele geçiliyor. |
| AC-4 (tümü başarısız → `[]`) | Değişmedi — döngü tükenince `return []` (mevcut davranış korundu). |
| AC-5 (Groq 429 → DeepSeek) | Key rotasyonu tükenince artık uzun bekleme yerine doğrudan `break` ile sıradaki modele (DeepSeek) geçiliyor. |
| AC-6 (`provider` alanı) | `_track_spend()`'de `model_name` içinde `"deepseek"` geçiyorsa `provider="deepseek"`, aksi halde `provider="groq"`; `ai_spend_history.json` kaydına eklendi. |

## Bulunan ve düzeltilen 2 ek sorun (orijinal plan.md'nin ötesinde, review sırasında yakalandı)
1. **Gerçek bug (plan.md'de öngörülmüştü, doğrulandı ve düzeltildi):** Stage 1'in "diğer sağlayıcı" dalı `model=self.model_fast` (hardcoded) kullanıyordu, döngü değişkeni `model_to_use`'u DEĞİL — artık `model=model_to_use` düzeltildi.
2. **Yanlış Groq fiyatlandırması (review sırasında yakalandı, plan.md'de yoktu):** İlk implementasyon denemesinde `llama-3.1-8b-instant` için $0.075/$0.30 (Gemini Flash fiyatı) yanlışlıkla kopyalanmıştı — gerçek Groq fiyatı ($0.05/$0.08 per 1M, bu oturumda WebSearch ile doğrulanmıştı) ile düzeltildi.

## Yan etki (istenmeyen değil, olumlu)
`_resolve_neighborhood_async()` fonksiyonu önceden `_get_async_client()` (Groq client) ile `self.model_fast` (`'deepseek-v4-flash'` — Groq'ta olmayan bir model adı) çağırıyordu; bu önceden var olan, bu görevin kapsamında OLMAYAN bir bug'dı. `self.model_fast`'in artık gerçek bir Groq modeline (`'llama-3.1-8b-instant'`) işaret etmesiyle bu fonksiyon da yan etki olarak doğru çalışır hale geldi — bilinçli bir değişiklik değil, sabit yeniden adlandırmasının pasif sonucu.

## Test Sonucu (bağımsız doğrulandı)
```
python -m pytest tests/test_deepseek_cost_fix.py -v
9 passed in ~17s
```

## CAVEMAN / Definition of Done kontrolü
- Yeni dosya yok, yeni soyutlama/yardımcı fonksiyon yok — mevcut döngü deseni Stage 1'e kopyalandı (Stage 1 ve Stage 2 arasında ortak bir yardımcı fonksiyon çıkarılmadı; CAVEMAN ilkesi gereği bu bilinçli bir tercih — iki kullanım yeri için soyutlama gerekli görülmedi).
- TODO/FIXME/placeholder yok.
- Kapsam dışı hiçbir şeye dokunulmadı (Stage1+Stage2 mimarisi birleştirilmedi, Gemini'ye geçilmedi, bakiye otomasyonu eklenmedi).
- Küçük bir kozmetik yorum-satırı hatası var (satır ~113 civarı: "$0.05/$0.08 per 1M (70b) or ... (70b)" — "(8b)" yerine yanlışlıkla "(70b)" yazılmış) — fonksiyonel etkisi yok, düzeltilmedi (önemsiz).

## Sıradaki adım
`verify` — gerçek test/lint/build gate'lerini çalıştıracak.
