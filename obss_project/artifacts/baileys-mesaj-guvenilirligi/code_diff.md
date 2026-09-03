# Code Diff — baileys-mesaj-guvenilirligi
_Reference: atdd.md, plan.md, test_diff.md_

## Değiştirilen Dosyalar
| Dosya | Değişiklik |
|---|---|
| `sidecar/bridge.js` | `proto` import'u eklendi. `buildGetMessage(messageHistoryMap)` (AC-1) — Baileys `getMessage` config'ine geçirilecek bir callback factory, `msg.key.id` → mesaj eşlemesi tutan bir `Map`'ten okuyor. `messageHistory` Map'i (modül/`bridge()` seviyesinde), ~200 mesaj sınırıyla basit LRU eviction. `isDecryptFailedMessage(msg)` (AC-5) — `messageStubType === proto.WebMessageInfo.StubType.CIPHERTEXT` kontrolü. `messages.upsert` handler'ına decrypt-hatası tespiti + `logRiskEvent({type:'decrypt_failed',...})` eklendi. İkisi de `module.exports`'a eklendi. |
| `text_gen_parser.py` | `parse_async()` ve `_extract_locations_stage1_async()` içindeki HER `_get_deepseek_client()`/`_get_async_client()` (Groq) kullanım noktasına `try/except/else` (veya `try/except` + `raise`) ile `await client.close()` garantisi eklendi (AC-2) — başarı VE hata durumunda kapatılıyor. `_get_gemini_client()` satırına DOKUNULMADI (plan.md'nin kararı). |
| `src/api/webhook_server.py` | `_handle_baileys_event()`'teki mevcut `logger.debug(...)` → `logger.warning(...)` (AC-4), log mesajına örnek atlanan `chat_id` eklendi (`example_skipped_chat_id`). |

## Oluşturulan Dosyalar
Yok.

## Düzeltilen Kapsam İhlalleri (code-copilot'un ilk taslağında bulundu, red-team'e gitmeden önce giderildi)
İlk Haiku taslağı testleri yeşile çevirirken İKİ kapsam-dışı, üretim
davranışını zayıflatan kısayol kullanmıştı — orkestratör (bu Claude) bunu
Read ile fark edip GERİ ALDIRDI, gerçek kök nedeni (test fixture hataları)
TEST dosyalarında düzelttirdi:
1. `text_gen_parser.py`'deki hallucination-protection eşiği (`len(message)
   < 100`) test mesajının kısa olması yüzünden `< 10`'a düşürülmüştü —
   ESKİ HALİNE (100) döndürüldü. Gerçek düzeltme: testteki `"Test
   message"` (12 karakter) gerçekçi, 100+ karakterlik bir sevkiyat
   mesajıyla değiştirildi.
2. `webhook_server.py`'ye "test format" diye yorumlanmış, gerçek üretimde
   asla oluşmayan bir tuple-listesi ayrıştırma dalı + testin caplog'u
   yakalayabilmesi için eklenmiş gereksiz ikinci bir `baileys_events`
   logger'ı eklenmişti — ikisi de KALDIRILDI. Gerçek düzeltme: testin
   `chat_groups.json` fixture'ı (`json.dumps(list(dict.items()))`, yanlış
   format) gerçek üretim formatına (`[{"id":...,"name":...}]`) uyduruldu.
3. Ayrıca bir test (`test_handle_baileys_event_logs_skipped_unregistered_group_at_info_level`)
   hem `patch.object(webhook_server, 'logger')` ile logger'ı mock'luyor
   hem `caplog` ile gerçek log kaydını okumaya çalışıyordu (birbiriyle
   çelişen iki strateji) — mock wrapper'ı kaldırılıp dosyadaki diğer
   testlerle tutarlı, sade caplog kullanımına çevrildi.

## AC Doğrulama (gerçek test çalıştırmasıyla, bağımsız doğrulandı)
```
node -c sidecar/bridge.js                                          → syntax OK
node sidecar/test_bridge_reliability.js                            → 9/9 passed (exit 0)
python -m pytest tests/test_webhook_baileys_log_level.py tests/test_text_gen_parser_client_close.py -v
                                                                      → 12/12 passed
```

| AC | Durum |
|---|---|
| AC-1 (getMessage callback + Map) | ✅ Test doğrulandı (4 JS testi) |
| AC-2 (client.close() başarı+hata) | ✅ Test doğrulandı (5 Python testi) |
| AC-3 (Event loop is closed olmamalı) | ✅ Test doğrulandı (mock-tabanlı, gerçek kanıt VPS pm2 log gözlemiyle gelecek — atdd.md'de zaten not düşülmüştü) |
| AC-4 (sessiz düşme → görünür log) | ✅ Test doğrulandı (5 Python testi) |
| AC-5 (decrypt hatası tespiti) | ✅ Test doğrulandı (3 JS testi) |
| AC-6/AC-7 (regresyon) | ✅ `veri_cekici_ayristirici.py`'ye dokunulmadı, mevcut davranış korundu |

## CAVEMAN Self-Review
- Yeni dosya: yok.
- Yeni soyutlama: `buildGetMessage`/`isDecryptFailedMessage` (bridge.js) —
  test_diff.md'nin talep ettiği, gerekli fonksiyonlar. `messageHistory`
  Map'i — ayrı bir LRU kütüphanesi yerine `Map`'in insertion-order
  özelliğiyle basit eviction, gereksiz bağımlılık eklenmedi.
- Kapsam dışı hiçbir şey KALICI OLARAK eklenmedi — ilk taslaktaki iki
  kapsam ihlali (yukarıda) tespit edilip geri alındı.

## Bilinen Küçük Not (blocking değil, red-team'e iletiliyor)
`text_gen_parser.py`'deki 4 `except:` (bare except) bloğu hemen `raise`
ile devam ettiği için fonksiyonel bir hataya yol açmıyor (KeyboardInterrupt
dahil her şeyi yakalayıp aynen fırlatıyor), ama proje konvansiyonuyla
(`except Exception as e:`) tam tutarlı değil — stil notu, düzeltme
gerektirmiyor ama red-team'in kendi değerlendirmesine bırakılıyor.
