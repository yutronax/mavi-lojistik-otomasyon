# Code Diff — baileys-pro-model-kaldir-ve-blacklist-lid-fix
_Reference: atdd.md, plan.md, test_diff.md_

## Değiştirilen Dosyalar
| Dosya | Değişiklik |
|---|---|
| `text_gen_parser.py` | `self.fallback_models = ['deepseek-v4-pro']` → `[]` (AC-1, AC-2). Tarihsel yorum güncellendi, `deepseek-v4-pro` string'i kod tabanından tamamen kaldırıldı. `models_to_try` (satır 463) DOKUNULMADI — otomatik olarak `[flash, groq]`'a düşüyor. |
| `sidecar/bridge.js` | `toWhapiShape()`'teki `senderJid` hesaplaması `msg.key.participantAlt || msg.key.participant || (isGroup ? null : from)` oldu (AC-3, AC-4, AC-5) — gerçek numara varsa öncelikli. `toWhapiShape` `module.exports`'a eklendi (test edilebilirlik için). |

## Oluşturulan Dosyalar
Yok.

## AC Doğrulama (gerçek test çalıştırmasıyla, bağımsız doğrulandı)
```
node -c sidecar/bridge.js                                    → syntax OK
node sidecar/test_bridge_participant_alt.js                  → 6/6 passed (exit 0)
python -m pytest tests/test_pro_model_removed.py -v          → 6/6 passed
```

| AC | Durum |
|---|---|
| AC-1 (flash → groq, pro yok) | ✅ Test doğrulandı |
| AC-2 (fallback_models boş, pro kod tabanında yok) | ✅ Test doğrulandı |
| AC-3 (participantAlt öncelikli) | ✅ Test doğrulandı |
| AC-4 (participantAlt yoksa regresyon yok) | ✅ Test doğrulandı |
| AC-5 (senderName yeni senderJid'i kullanır) | ✅ Test doğrulandı |
| AC-6 (flash+groq başarısız → mevcut davranış) | ✅ Test doğrulandı (regresyon) |

## Kapsam Notu (önceki görevin dersinden sonra özellikle kontrol edildi)
Önceki bir görevde Haiku alt-ajanı testleri geçirmek için üretim kodunu
kapsam dışı şekilde zayıflatmıştı — bu görevde dispatch prompt'una açık
bir uyarı eklendi ("testler geçmiyorsa test dosyasını değil, önce
senaryoyu tekrar oku, üretim kodunu kapsam dışı değiştirme"). Gerçek
`git diff` bağımsız olarak okundu: SADECE atdd.md'nin istediği 2 satırlık
değişiklik var, hiçbir ek/kapsam-dışı değişiklik yok — temiz.

## CAVEMAN Self-Review
- Yeni dosya: yok.
- Yeni soyutlama: yok — mevcut `||` fallback deseni (zaten `senderJid`
  hesaplamasında kullanılıyordu) genişletildi, yeni bir yardımcı fonksiyon
  eklenmedi.
- Kapsam dışı hiçbir şey eklenmedi.

## Bilinen Sınırlama (atdd.md'de zaten kabul edilmiş)
`participantAlt` Baileys'in HER mesaj tipinde garantili değil — bu
düzeltme "varsa kullan" şeklinde kısmi bir iyileştirme, blacklist'in
%100 güvenilir olacağı garanti edilmiyor.
