# Plan — baileys-mesaj-guvenilirligi
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| `sidecar/bridge.js` | AC-1: `makeWASocket()`'e `getMessage` callback + son ~200 mesajı tutan in-memory Map eklenir (retry desteği). AC-5: `messages.upsert` handler'ına, Baileys'in decrypt hatasında `fullMessage.messageStubType = proto.WebMessageInfo.StubType.CIPHERTEXT` set ettiği (kaynak: `node_modules/@whiskeysockets/baileys/lib/Utils/decode-wa-message.js:296-298`) doğrulandı — bu tip mesajlar şu an `if (!msg.message) continue;` ile SESSİZCE atlanıyor, hiç loglanmıyor. `messageStubType === CIPHERTEXT` kontrolü eklenip `logRiskEvent({type:'decrypt_failed', ...})` çağrılmalı. | medium |
| `src/api/webhook_server.py` | AC-4: `_handle_baileys_event()` (satır 84-86) mevcut `logger.debug` → `logger.info`/`logger.warning` seviyesine çıkarılır (üretimde varsayılan log seviyesinde görünür olması için). | low |
| `text_gen_parser.py` (proje kökü, `src/` altında DEĞİL) | AC-2/AC-3 **[DÜZELTİLDİ]**: `_get_deepseek_client()` (satır 88-93, `AsyncOpenAI`), `_get_async_client()` (satır 83-86, `AsyncGroq`), `_get_gemini_client()` (satır 95-109, `google_genai.Client`) her çağrıda TAZE client döndürüyor ve hiçbiri kullanım sonrası kapatılmıyor. `parse_async()` (satır 324+, asıl çağrı noktası satır 457-501) içindeki her `client = self._get_*_client()` sonrası `try/finally` ile `await client.close()` eklenmeli (AsyncOpenAI/AsyncGroq'un `.close()` metodu var — google-genai `Client`'ın senkron sarmalayıcısı `asyncio.to_thread` ile çağrıldığı için (satır 465) onun kapatma ihtiyacı ayrıca doğrulanmalı, bkz. Open Questions). | high — hata mesajının doğrudan kaynağı burası, ama retry/model-fallback döngüsünün (satır 457-590) mantığını bozmadan sadece "kapat" eklemek gerekiyor |

## New Files
Yok.

## Dependencies
- `sidecar/bridge.js`: `@whiskeysockets/baileys`'in `proto` export'u (`makeWASocket` ile aynı import satırından `proto` da alınabilir — kütüphane zaten `require('@whiskeysockets/baileys')` içinde `proto` içeriyor, `WAProto` olarak da bilinir).
- `text_gen_parser.py`: `openai.AsyncOpenAI` ve `groq.AsyncGroq`'un ikisi de `async def close(self)` / `async with` destekliyor (her iki SDK de httpx tabanlı, standart pattern). `google_genai.Client`'ın senkron `models.generate_content` metodu zaten `asyncio.to_thread` ile ayrı bir thread'de çalıştırılıyor (satır 465-469) — bu çağrı yolu muhtemelen "Event loop is closed" hatasının asıl kaynağı DEĞİL (senkron client, kendi iç yönetimini yapıyor); asıl şüpheli `AsyncOpenAI`/`AsyncGroq` (satır 473-501), çünkü `model_robust`/`model_deepseek`/`model_gemini` hepsi artık `'deepseek-v4-flash'`e alias'landığı için (satır 73-75) DeepSeek yolu (AsyncOpenAI) en sık çalışan koddur — üretimde en çok bu tetikleniyor olmalı.

## Migration Required?
Hayır — hiçbir dosya schema/DB değişikliği içermiyor, düz kod değişikliği.

## Risks
- (atdd.md'den) `getMessage` decrypt kaybını garanti çözmüyor — kütüphane
  seviyesi LID/Signal senkronizasyon sınırlaması.
- **YENİ (plan adımında bulundu):** `text_gen_parser.py`'deki retry/model-
  fallback döngüsü (satır 457-590) karmaşık — aynı `for attempt in
  range(3)` döngüsü içinde birden fazla `client = self._get_*_client()`
  çağrısı var (rate-limit sonrası farklı key ile tekrar çağrılabiliyor).
  `close()` eklerken HER `continue`/`break`/exception yolunda da client'ın
  kapatıldığından emin olunmalı — sadece happy-path'e `close()` eklemek
  yetmez, aksi halde bazı hata yollarında client hâlâ sızabilir. Bu yüzden
  code-copilot'a "her `client = self._get_*_client()` atamasından sonra
  try/finally ile kapat" talimatı NET verilmeli.
- **YENİ:** `google_genai.Client`'ın (satır 464, 465-469) kapatılması
  gerekip gerekmediği doğrulanmadı — `asyncio.to_thread` ile senkron
  çağrıldığı için async client kapatma sorunundan muaf olabilir. code-
  copilot bu satırı DOKUNMADAN bırakmalı (sadece AsyncOpenAI/AsyncGroq
  yollarına close eklensin), red-team bunu ayrıca doğrulasın.

## Kararlar (orkestratör tarafından kod okumasıyla doğrudan çözüldü — Haiku/omni'ye gerek kalmadı)
1. **`google_genai.Client` kapatılsın mı?** → HAYIR, DOKUNULMASIN. Bu
   projenin venv'inde `google-genai` paketi bu worktree'de kurulu değil
   (doğrulanamadı), ayrıca bu client `asyncio.to_thread` ile senkron
   çağrılıyor (satır 465-469) — async client sızıntısı riski taşıyan
   `AsyncOpenAI`/`AsyncGroq` yolundan (satır 473, 488) mimarisel olarak
   farklı. code-copilot SADECE `_get_deepseek_client()` ve
   `_get_async_client()` (Groq) sonuçlarına `close()` eklesin; satır
   464-469'daki gemini client çağrısı DEĞİŞTİRİLMESİN.
2. **`sidecar/bridge.js`'de `proto` import yolu** → Doğrulandı:
   `@whiskeysockets/baileys` paketinin kök `index.js`'i
   `export * from '../WAProto/index.js'` yapıyor ve `WAProto/index.js`
   `export const proto = ...` ile `proto`'yu named export olarak
   sunuyor. Yani bridge.js'teki mevcut satır:
   `const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');`
   sadece `proto` eklenerek genişletilmeli:
   `const { default: makeWASocket, useMultiFileAuthState, DisconnectReason, proto } = require('@whiskeysockets/baileys');`
   Kullanım: `msg.messageStubType === proto.WebMessageInfo.StubType.CIPHERTEXT`.
