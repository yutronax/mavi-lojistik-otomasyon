# Baileys POC Sidecar (Saga epic #42)

Whapi.cloud'dan ($35/ay) Baileys'e (ücretsiz) geçiş denemesi — sadece POC
aşaması. **Asıl üretim WhatsApp numarasıyla ASLA çalıştırmayın.**

## Kurulum

```bash
cd sidecar
npm install
```

## Çalıştırma

```bash
npm run poc
```

1. Terminalde bir QR kod belirir.
2. **Test/ikincil bir WhatsApp hesabıyla** telefonda: Ayarlar → Bağlı
   Cihazlar → Cihaz Bağla → QR'ı taratın.
3. Bağlandıktan sonra script otomatik olarak katıldığınız grupları listeler
   (`poc_groups.json`'a yazılır).
4. Test grubuna bir mesaj gönderin (başka bir telefondan) — `poc_messages.log`
   dosyasına ve konsola düşmeli.

## Güvenlik notu

`auth_info_baileys/` klasörü, WhatsApp hesabınıza **oturum açık** anlamına
gelen kimlik dosyalarını içerir — bu, hesabın şifresi gibi davranır.
`.gitignore`'a eklendi, asla commit etmeyin veya paylaşmayın.

## bridge.js — webhook köprüsü (epic #43)

`connect.js` sadece POC/test için (log dosyasına yazar). `bridge.js`,
aynı bağlantı mantığını kullanır ama mesajları gerçek sisteme
(`src/api/webhook_server.py`'nin yeni `/baileys-webhook` endpoint'i
üzerinden) gönderir.

**Önkoşul:** `webhook_server.py` çalışıyor olmalı (varsayılan port 8080).
Ana uygulamayı (`src/gui/masaustu_uygulama.py`) açtığınızda bu zaten
otomatik başlıyor olmalı — ayrıca kontrol edin.

```bash
node bridge.js
```

Mesajlar `convert_whapi_message()` ile aynı şekle (`id`, `body`,
`chat_id`, `chat_name`, `sender_name`, `from`, `timestamp`) dönüştürülüp
POST edilir. Python tarafı:
1. Sadece `data/chat_groups.json`'da kayıtlı gruplardan gelenleri işler
   (212 test grubundan sadece kayıtlı olanlar geçer — Gemini maliyeti
   kontrolü için).
2. `chat_name`'i `chat_groups.json`'dan otomatik zenginleştirir.
3. `orchestrator.add_to_processing_queue()`'ya doğrudan verir — Whapi
   REST'e geri dönüp yeniden çekmez (Baileys mesajı zaten tam halde
   geliyor).

Metin çıkarılamayan mesajlar (`extractText()` `null` dönerse) gönderilmez,
`bridge_unhandled_messages.log`'a ham JSON olarak yazılır.

**Test edilen (mock orchestrator ile, Python tarafında):**
- Kayıtlı bir grup ID'siyle mesaj → doğru filtrelendi, `chat_name`
  zenginleştirildi, kuyruğa eklendi. ✅
- Kayıtlı olmayan bir grup ID'siyle mesaj → filtrelendi, kuyruğa
  eklenmedi. ✅

**Test EDİLMEYEN (gerçek uçtan uca, kullanıcı gerektirir):**
- `bridge.js`'in gerçekten çalışan bir `webhook_server.py`'ye canlı HTTP
  isteği atması ve gerçek bir WhatsApp mesajının uçtan uca (Baileys →
  bridge.js → webhook_server.py → orchestrator kuyruğu → parser) akması.

## Durum

- [x] Node.js projesi + Baileys kurulumu (epic #42)
- [x] Bağlantı script'i (`connect.js`) — gerçek QR taratma ve mesaj alma
      kullanıcı tarafından doğrulandı (epic #42, TAMAMLANDI)
- [x] Webhook köprüsü (`bridge.js`) + `webhook_server.py` `/baileys-webhook`
      endpoint'i yazıldı, mantık mock ile test edildi (epic #43)
- [ ] **Gerçek uçtan uca test — `webhook_server.py` çalışırken `bridge.js`
      ile gerçek bir mesajın kuyruğa düştüğünü doğrulamak, kullanıcı
      gerektirir**
