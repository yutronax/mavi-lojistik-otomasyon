# Test Diff — baileys-grup-listesi
_Reference: atdd.md, plan.md_

## Oluşturulan Dosyalar
| Dosya | Framework | Çalıştırma |
|---|---|---|
| `tests/test_baileys_groups_panel.py` | pytest, `admin_panel.app.test_client()` | `python -m pytest tests/test_baileys_groups_panel.py -v` → **14/14 failed** (gerçek, `AttributeError: BAILEYS_GROUPS_PATH` — implementasyon henüz yok) |
| `sidecar/test_baileys_groups_state.js` | Node builtin `assert` | `node sidecar/test_baileys_groups_state.js` → **exit code 1** (gerçek, `writeGroupsState` export edilmemiş) |

## Bulunan ve Düzeltilen Sorun (test-copilot'un dosyasında, implementasyonda değil)
İlk taslak `test_baileys_groups_state.js`, `writeGroupsState` export edilmediğinde her testi "SKIPPED" yazıp atlıyor ve sonunda **"✓ ALL TESTS PASSED"** diyerek sahte bir yeşil üretiyordu — implementasyon hiç yokken bile "başarılı" görünüyordu. `test_baileys_qr_state.js`'deki doğru desen (export yoksa `process.exit(1)` ile sert başarısızlık) uygulanarak düzeltildi. Bağımsız olarak doğrulandı: artık `exit code 1`.

## AC → Test Eşlemesi
| AC | Davranış | Python Testi | JS Testi |
|---|---|---|---|
| AC-1 | bridge.js periyodik tarama, `writeGroupsState` dönüşümü (`subject`→`name`) | — | `testWriteGroupsState` |
| AC-2 | `/api/whatsapp/groups` → 200 + `{"groups":[...],"cached":true}`, `saved` alanı | `TestGroupsPanelHappyPath`, `TestGroupsPanelSavedField::test_saved_field_calculation` | `testResponseStructure` |
| AC-3 | Baileys bağlı değil → 202 | `TestGroupsPanelNotAuthenticated` | — |
| AC-4 | Dosya yok → 202 | `TestGroupsPanelNoSource` | — |
| AC-5 | Bridge hatası → dosya bozulmaz | — | `testAtomicWrite`, `testConcurrentWriteProtection` |
| AC-6 | Bozuk JSON → 200 + `cached:false`, 500 yok | `TestGroupsPanelBrokenJson` | — |
| AC-7 | Yetkisiz erişim (mevcut desen) | `TestGroupsPanelAuth` (3 test) | — |

## code-copilot İçin Bağlayıcı Varsayımlar (test dosyalarından, birebir)
- **Python**: `admin_panel.BAILEYS_GROUPS_PATH = os.path.join(PROJECT_ROOT, "data", "baileys_groups.json")`; route `GET /api/whatsapp/groups`, `@require_auth`; `saved` alanı endpoint içinde `_load_groups()` sonucuyla karşılaştırılarak hesaplanır.
- **Node.js**: `writeGroupsState(groupsObject, filePath)` — `groupsObject` Baileys'in `{jid: GroupMetadata}` formatında, fonksiyon bunu `{"groups": [{"id":..., "name":...}]}` şekline çevirip atomic write ile yazar. `GroupMetadata.subject` → `name` alanına eşlenir (`name` DEĞİL, Baileys `subject` kullanıyor — plan.md'de doğrulandı). `module.exports`'a eklenmeli.
