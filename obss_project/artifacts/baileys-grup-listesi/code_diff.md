# Code Diff — baileys-grup-listesi
_Reference: atdd.md, plan.md, test_diff.md_

## Değiştirilen Dosyalar
| Dosya | Değişiklik |
|---|---|
| `sidecar/bridge.js` | `writeGroupsState(groupsObject, filePath)` fonksiyonu eklendi (Baileys'in `{jid: GroupMetadata}` objesini `{"groups":[{"id","name"}]}` dizisine çevirip `atomicWrite` ile yazıyor, `subject`→`name` eşlemesi doğru). `connection === 'open'` bloğuna 60 saniyelik `setInterval` ile periyodik `sock.groupFetchAllParticipating()` çağrısı eklendi (hata durumunda dosyaya dokunmuyor, sadece log). `module.exports`'a eklendi. |
| `src/api/admin_panel.py` | `BAILEYS_GROUPS_PATH` sabiti eklendi. Yeni route `GET /api/whatsapp/groups` (`@require_auth`) — sırayla: dosya yok→202, JSON bozuk→200/cached:false, Baileys bağlı değil→202, başarılı→200 + `saved` alanı hesaplanmış liste. Frontend: "Baileys Grupları" kartı, "Grupları Yenile" butonu, `loadBaileysGroups()`/`baileysGrpAdd()` JS fonksiyonları eklendi. |

## Oluşturulan Dosyalar
Yok — `data/baileys_groups.json` çalışma zamanında oluşacak.

## AC Doğrulama (gerçek test çalıştırmasıyla + canlı tarayıcı)
```
node sidecar/test_baileys_groups_state.js       → 7/7 passed (exit 0)
pytest tests/test_baileys_groups_panel.py -v    → 14/14 passed
pytest -q (tüm proje)                            → 118 passed (104 önceki + 14 yeni, regresyon yok)
```

| AC | Durum |
|---|---|
| AC-1 (writeGroupsState dönüşümü) | ✅ Test doğrulandı |
| AC-2 (happy path, saved alanı) | ✅ Test + **canlı tarayıcıda uçtan uca doğrulandı**: sahte 2 grup yazıldı, panelde göründü, "Ekle" tıklanınca gerçekten `data/chat_groups.json`'a eklendi ve listeden düştü |
| AC-3 (Baileys bağlı değil → 202) | ✅ Test doğrulandı |
| AC-4 (dosya yok → 202) | ✅ Test + canlı doğrulandı ("Gruplar henüz taranmadı..." mesajı göründü) |
| AC-5 (bridge hatası → dosya bozulmaz) | ✅ Test doğrulandı (atomic write) |
| AC-6 (bozuk JSON → 200/cached:false, 500 yok) | ✅ Test doğrulandı |
| AC-7 ("Grupları Yenile" butonu) | ✅ Canlı doğrulandı, buton render oluyor |

## Canlı Doğrulama Notu
Frontend değiştiği için (önceki görevlerde bu dosyada JS-kaçış hataları bulunmuştu) yerel sunucu başlatılıp gerçek tarayıcıda test edildi: sıfır konsol hatası, "Ekle" akışı gerçek bir kayıt oluşturup UI'yı güncelledi. Test sırasında oluşan geçici veri (`data/chat_groups.json`'a eklenen test grubu, `basarisiz_gonderimler.json` yan etkisi) doğrulama sonrası geri alındı.

## CAVEMAN Self-Review
- Yeni dosya: yok.
- Yeni soyutlama: yok — mevcut `atomicWrite()`, `_load_groups()`, `require_auth`, `confirm()`/`toast()`/`api()` desenleri reuse edildi.
- Kapsam dışı hiçbir şey eklenmedi (grup üyeleri, grup yönetimi, flag-tetikleme mekanizması yok — sadece periyodik 60sn tarama).
