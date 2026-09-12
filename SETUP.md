# SETUP — maviLojistik

Yeni ortam değişkenleri, kurulum adımları ve manuel doğrulama adımları —
`commit` skill'inin 2b adımı tarafından `plan.md`'den doğrudan aktarılır
(bkz. `commit/SKILL.md` 2b, 2026-09-12). Üzerine eklenir, geçmiş kayıt silinmez.

---

## Webhook Kimlik Doğrulama (Task #379 — strix-guvenlik-acigi-duzeltme, 2026-09-12)

**Yeni ortam değişkeni:** `WEBHOOK_SHARED_SECRET`

`.env.example`'a eklendi (kaynak: `plan.md` Dependencies): `src/api/
webhook_server.py`'nin `do_POST`'u artık gelen `X-Webhook-Secret` header'ını
bu değerle `secrets.compare_digest` ile karşılaştırıyor, eşleşmezse 403
dönüyor.

**Manuel kurulum adımı (production'a çıkmadan önce zorunlu):**
1. Gerçek bir secret üret: `python -c "import secrets; print(secrets.token_hex(32))"`
2. `.env`'e `WEBHOOK_SHARED_SECRET=<üretilen değer>` olarak ekle.
3. **Sıra kritik** (kaynak: `atdd.md` Rollback Beklentisi): Baileys sidecar
   köprüsü ve Whapi webhook kaydı bu header'ı göndermek üzere güncellenmeden
   bu kod production'a çıkarsa, gerçek webhook trafiği 403 ile kesintiye
   uğrar. Önce sidecar/Whapi tarafını güncelle, ondan sonra bu secret'ı
   zorunlu hale getir.

Bu adım henüz tamamlanmadı — sidecar/Whapi güncellemesi ayrı bir görev
olarak açılmalı (bkz. `atdd.md` Kapsam Dışı).

---

## Strix (Pentest) Altyapısı — OpenRouter/OmniRoute Ayarı (Task #377, 2026-09-12)

**Ortam değişkeni düzeltmesi:** `STRIX_LLM`

Windows User seviyesi ortam değişkeni (`setx STRIX_LLM "openai/auto/
best-coding"`) — `openai/auto/best-free` KULLANILMASIN, tool-calling
desteklemeyen sağlayıcılara düşüp taramayı çöktürüyor. `openai/auto/best`
diye bir combo YOK (geçersiz). `~/.strix/cli-config.json`'u elle düzenlemek
kalıcı değildir — dosya her çalıştırmada aktif env var'a göre yeniden
yazılır, gerçek kaynak Windows ortam değişkenidir. Değişiklik yeni bir
terminal oturumunda etkili olur.

**Doğrulama komutu (yeni bir terminalde):**
```bash
export PATH="$HOME/.strix/bin:$PATH"
strix --target <hedef-dizin> -m quick -n --max-turns 25 --max-budget 2
```

Detaylı tuzaklar (aynı hedefe ikinci tarama sessizce çıkar, model kalite
uyarısı vb.): `~/.claude/skills/strix-scan/SKILL.md`.
