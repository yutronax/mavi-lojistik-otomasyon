# Plan — deepseek-max-tokens-cap
_Reference: atdd.md_

## Kod keşfi — mevcut durum (satır numaraları teyit edildi)
- Satır 279: Stage 1 DeepSeek çağrısı (`create(model=..., messages=..., temperature=0.0)`) — `max_tokens` YOK.
- Satır 290-294: Stage 1 Groq çağrısı (`create(..., temperature=0.0, reasoning_effort="low")`) — `max_tokens` YOK.
- Satır 465-469: Stage 2 DeepSeek çağrısı (`create(..., temperature=0.0, response_format={"type": "json_object"})`) — `max_tokens` YOK.
- Satır 476-481: Stage 2 Groq çağrısı (`create(..., temperature=0.0, response_format=..., reasoning_effort="low")`) — `max_tokens` YOK.
- Satır 818-822: ALAKASIZ küçük bir yardımcı çağrı, zaten `max_tokens=20` içeriyor — DOKUNULMAYACAK, sadece referans (projenin zaten bu parametreyi kullandığının kanıtı, yeni bir desen icat edilmiyor).

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| text_gen_parser.py | 4 API çağrı noktasına (satır 279, 290, 465, 476) `max_tokens=1500` parametresi eklemek (AC-1, AC-2) | low |

## New Files
Yok.

## Dependencies
- `openai`/OpenAI-uyumlu SDK client'ları (`_get_deepseek_client()`, `_get_async_client()`) — her ikisi de standart `chat.completions.create()` imzasını kullanıyor, `max_tokens` bu imzanın standart bir parametresi (satır 818-822'de zaten kullanılıyor, kanıtlanmış).
- Mevcut JSON-parse-hatası → fallback mantığı (Stage 1: satır ~299 sonrası `except`, Stage 2: benzer yapı) — DEĞİŞTİRİLMİYOR, kesilmiş JSON zaten bu mekanizmayı doğal olarak tetikleyecek.

## Migration Required?
Hayır.

## Risks
_(atdd.md'den taşındı)_
- `max_tokens=1500`, gerçekten 10+ rotalı bir mesajı kesip fallback'e düşürebilir — veri kaybı değil, mevcut fallback'e yönlendirme (kabul edilebilir taviz, atdd.md'de zaten kabul edildi).
- Cap, runaway'in kök nedenini çözmüyor, sadece üst sınırı koyuyor (kapsam dışı, atdd.md'de not düşüldü).

## Kararlar (açık soru yoktu — kod keşfi netti, Haiku dispatch'ine gerek kalmadı)
1. **Log satırı nereye eklenecek?** `truncated_at_max_tokens` logu, JSON parse hatasının yakalandığı `except` bloğunun içine, mevcut hata logunun yanına eklenecek — yeni bir kontrol akışı icat edilmeyecek, sadece JSON parse hatası mesajına `finish_reason` bilgisi (varsa) eklenerek kesilmenin ayırt edilmesi sağlanacak. `response.choices[0].finish_reason == 'length'` kontrolü, OpenAI-uyumlu API'lerin standart bir alanı — bu, "gerçekten kesildi mi yoksa başka bir JSON hatası mı" ayrımını yapmanın en doğru yolu.
2. **4 çağrının hepsine aynı `max_tokens=1500` mi?** Evet — atdd.md AC-1/AC-2 ile birebir, model-agnostik güvenlik ağı.

## Open Questions
Yok — kod keşfi ve atdd.md'nin kendi "Sorular ve Cevaplar" bölümü yeterli, ek karar gerekmedi.
