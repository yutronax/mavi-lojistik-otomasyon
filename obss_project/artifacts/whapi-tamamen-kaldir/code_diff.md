# Code Diff — whapi-tamamen-kaldir
_Reference: atdd.md (AC-3/AC-7 düzeltilmiş), plan.md, test_diff.md_

## Değiştirilen Dosyalar
| Dosya | Değişiklik |
|---|---|
| `src/api/admin_panel.py` | `/api/whatsapp-health` route'u (Whapi health check, `gate.whapi.cloud/health`) ve `/api/groups/available` route'u (Whapi grup listeleme, `gate.whapi.cloud/groups`) + `_grp_cache` değişkeni TAMAMEN silindi. Frontend: `wa-health-badge`, "Whapi'dan Yeniden Çek" butonu, "kayıtsız grup" listesi bölümü, `checkWaHealth()`/`loadAvailableGroups()`/`grpAdd()` JS fonksiyonları silindi. `loadGrpTab()`/`grpDel()`'deki bu fonksiyonlara yapılan çağrılar temizlendi. (149 satır silindi, 11 satır eklendi net.) |
| `src/parsers/veri_cekici_ayristirici.py` | `handle_webhook_event()`'in başına `if not WHAPI_POLLING_ENABLED: return` gate'i eklendi (5 satır) — Whapi'nin eski bir webhook kaydı hâlâ VPS'e push yaparsa bile artık `fetch_all_messages()` (canlı Whapi API çağrısı) tetiklenmiyor. |

## Dokunulmayan Dosyalar (bilinçli, plan.md'ye göre)
- `src/fetchers/whapi_fetcher.py` — GUI kullanıyor, silinmedi (test: `test_whapi_fetcher_module_importable` ile hâlâ import edilebildiği doğrulandı).
- `src/api/webhook_server.py` — GUI ile paylaşılan dosya, hiç dokunulmadı.
- `vps_main.py`, `.env` — hiç dokunulmadı.
- `/api/groups` (kayıtlı gruplar), Baileys QR bölümü, "Bağlantıyı Kes" butonu — değişmedi.

## AC Doğrulama (gerçek test çalıştırmasıyla + canlı tarayıcı)
```
pytest tests/test_whapi_removed.py -v   → 14 passed
pytest -q (tüm proje)                    → 104 passed (90 önceki + 14 yeni, regresyon yok)
```

| AC | Durum |
|---|---|
| AC-1 (`/api/groups/available` silindi) | ✅ Test + canlı network isteklerinde hiç görünmüyor |
| AC-2 (`/api/whatsapp-health` silindi) | ✅ Test + canlı doğrulandı |
| AC-3 düzeltilmiş (`handle_webhook_event` gate) | ✅ Test doğrulandı (`fetch_all_messages` çağrılmıyor) |
| AC-5 (`/api/groups` regresyon) | ✅ Test + canlı tarayıcıda "Kayıtlı Gruplar" listesi normal render oluyor |
| AC-6 (grep: sıfır aktif Whapi çağrısı) | ✅ Test doğrulandı |

## Canlı Doğrulama Notu
Frontend HTML/JS değiştiği için (önceki görevlerde bu dosyada bir JS-kaçış hatası canlı testte bulunmuştu) yerel sunucu başlatılıp gerçek tarayıcıda giriş yapılıp Gruplar sekmesi açıldı: konsol hatası yok (sadece zararsız favicon 404), network isteklerinde silinen iki route'a hiç istek gitmiyor, "Kayıtlı Gruplar" ve Baileys QR bölümleri bozulmadan render oluyor.

## Bulunan ve Düzeltilen Test Sorunları (test-copilot'un dosyasında, implementasyonda değil)
1. İlk test taslağı `ImportError: cannot import name 'genai' from 'google'` ile collection'da çöküyordu — projenin mevcut `sys.modules` stub deseni (`test_dedup_active_ids_fix.py`'den) eklenerek düzeltildi.
2. İki test `/api/groups/available` için `404` bekliyordu, ama Flask `/api/groups/<path:group_id>` (DELETE) route'unun URL kalıbı çakışması yüzünden doğru şekilde `405` dönüyordu (route gerçekten silinmiş, sadece HTTP durum kodu beklentisi yanlıştı) — `assert status in (404, 405)` olarak düzeltildi.

## CAVEMAN Self-Review
- Yeni dosya: yok.
- Yeni soyutlama: yok — sadece silme + tek satırlık early-return gate.
- Kapsam dışı hiçbir şey eklenmedi/değiştirilmedi.
- Mevcut proje desenleri (Flask route yapısı, `WHAPI_POLLING_ENABLED` flag'i) birebir korundu.
