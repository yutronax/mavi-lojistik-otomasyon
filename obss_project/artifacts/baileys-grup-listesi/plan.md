# Plan — baileys-grup-listesi
_Reference: atdd.md_

## Files to Modify
| File | Why | Risk |
|------|-----|------|
| sidecar/bridge.js | `writeGroupsState()` fonksiyonu eklenir (`writeQrState`'in aynı `atomicWrite()` yardımcı fonksiyonunu kullanan yeni bir fonksiyon). `connection === 'open'` sonrası bir `setInterval(..., 60000)` başlatılır — her tetiklendiğinde `sock.groupFetchAllParticipating()` çağrılır, sonucu `data/baileys_groups.json`'a yazılır. AC-1, AC-5. | low |
| src/api/admin_panel.py | Yeni route `GET /api/whatsapp/groups` (`@require_auth`, mevcut `/api/whatsapp/qr` route'unun hemen yanına). `INDEX_HTML`'e "kayıtsız grup tara/ekle" bölümü (whapi-tamamen-kaldir'de silinenin benzeri HTML/JS, ama artık `/api/whatsapp/groups`'u çağırıyor) eklenir. AC-2, AC-3, AC-4, AC-6, AC-7. | medium (frontend + backend, canlı doğrulama gerekir) |

## New Files
Yok — `data/baileys_groups.json` çalışma zamanında bridge.js tarafından oluşturulacak (kod olarak eklenen bir dosya değil, `data/baileys_qr.json`'ın aynı deseni).

## Dependencies
- **Baileys API doğrulandı** (`sidecar/node_modules/@whiskeysockets/baileys/lib/Socket/groups.d.ts`): `groupFetchAllParticipating: () => Promise<{[_: string]: GroupMetadata}>` — bir DİZİ değil, JID'e göre anahtarlanmış bir OBJE döner. `GroupMetadata` (`lib/Types/GroupMetadata.d.ts`) `id: string` ve `subject: string` alanlarını içeriyor (grup adı `name` değil `subject`). bridge.js'in `writeGroupsState()` fonksiyonu bu objeyi `Object.values(...)` ile diziye çevirip `{id: g.id, name: g.subject}` şeklinde eşleyecek — atdd.md'nin varsaydığı `{"id":..., "name":...}` şeklini üretmek için bu dönüşüm ZORUNLU (atdd.md'nin Unknowns bölümündeki soru netleşti).
- `sidecar/bridge.js`'in mevcut `atomicWrite()` yardımcı fonksiyonu (panel-baileys-qr-gosterimi görevinden, satır ~117-127) — yeni soyutlama eklenmeden doğrudan kullanılacak.
- `admin_panel.py`'nin mevcut `_load_groups()` yardımcı fonksiyonu (kayıtlı grupları `data/chat_groups.json`'dan okuyan, `/api/groups` route'unun kullandığı) — yeni route'ta `saved` alanını hesaplamak için AYNI fonksiyon çağrılacak, tekrar kod yazılmayacak.
- `admin_panel.py`'nin mevcut `BAILEYS_QR_PATH` sabit deseni — yeni bir `BAILEYS_GROUPS_PATH = os.path.join(PROJECT_ROOT, "data", "baileys_groups.json")` sabiti aynı yere eklenecek.

## Migration Required?
No — şema/veri değişikliği yok, sadece yeni bir çalışma-zamanı JSON dosyası.

## Risks
(atdd.md'den taşındı, kod keşfiyle netleşti)
- **[Netleşti]** `groupFetchAllParticipating()`'in dönüş şekli (obje, dizi değil) atdd.md'de "Unknown" olarak işaretlenmişti — artık netleşti, plan'a işlendi. `test-copilot`/`code-copilot` bu dönüşümü (`Object.values` + `subject`→`name` eşlemesi) doğru yapmalı, aksi halde AC-1/AC-2 karşılanmaz.
- 60 saniyelik periyodun gerçek Baileys rate-limit davranışıyla çakışıp çakışmayacağı hâlâ doğrulanmadı (atdd.md'nin bilinen riski) — `verify` adımında canlı test edilemez (yerel ortamda gerçek Baileys bağlantısı yok), bu risk kabul ediliyor.
- Frontend değişikliği (`INDEX_HTML`) — önceki görevlerde bu dosyada canlı testte JS hataları bulunmuştu (panel-baileys-qr-gosterimi, whapi-tamamen-kaldir). `verify` adımında AYNI titizlikle canlı tarayıcı testi ZORUNLU, gate 11/12 N/A değil aktif.

## Open Questions
Yok — atdd.md'nin tek "Unknown"u (Baileys API'nin dönüş şekli) kod okunarak netleşti, ek claude-omni/Haiku dispatch'ine gerek kalmadı.
