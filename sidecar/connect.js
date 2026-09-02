// Baileys POC — test/ikincil numarayla bağlantı doğrulama scripti.
// ASIL ÜRETIM NUMARASI İLE ÇALIŞTIRMAYIN — bu sadece POC/test aşaması içindir.
//
// Kullanım: node connect.js
// İlk çalıştırmada terminale bir QR kod basılır. Test WhatsApp hesabınızda
// Ayarlar > Bağlı Cihazlar > Cihaz Bağla ile bu QR'ı taratın.
// Bağlantı bilgisi ./auth_info_baileys/ klasörüne kaydedilir (sonraki
// çalıştırmalarda tekrar QR taratmanıza gerek kalmaz).

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const pino = require('pino');
const fs = require('fs');
const path = require('path');

const LOG_FILE = path.join(__dirname, 'poc_messages.log');

async function connect() {
  const { state, saveCreds } = await useMultiFileAuthState(path.join(__dirname, 'auth_info_baileys'));

  const sock = makeWASocket({
    auth: state,
    logger: pino({ level: 'warn' }),
    printQRInTerminal: false, // qrcode-terminal'i biz elle çağırıyoruz (kütüphane deprecated uyarısı veriyor)
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log('\n=== QR KODU (test WhatsApp hesabınızla taratın) ===\n');
      qrcode.generate(qr, { small: true });
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;

      if (statusCode === DisconnectReason.connectionReplaced) {
        console.log('[BAGLANTI KAPANDI] statusCode=440 (conflict/replaced) — YENIDEN BAGLANMIYOR.');
        console.log('[UYARI] Bu oturumu kullanan başka bir bağlantı algılandı. Diğer bağlantıyı kapatıp scripti elle yeniden başlatın.');
        return;
      }

      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`[BAGLANTI KAPANDI] statusCode=${statusCode} yenidenBaglan=${shouldReconnect}`);
      if (shouldReconnect) {
        setTimeout(connect, 2000);
      } else {
        console.log('[OTURUM KAPANDI] auth_info_baileys/ klasörünü silip yeniden QR taratmanız gerekir.');
      }
    } else if (connection === 'open') {
      console.log('[BAGLANDI] Baileys WhatsApp bağlantısı aktif. Mesaj bekleniyor...');
    }
  });

  // Bir Baileys mesaj objesinden düz metni çıkarır. Baileys v7'de metin,
  // mesaj tipine göre farklı alanlarda bulunabilir (conversation,
  // extendedTextMessage, ephemeralMessage/viewOnceMessage sarmalayıcıları,
  // caption'lı medya vb.) — tek bir alana bakmak "[metin dışı mesaj]"
  // yanlış negatifine yol açar (bu POC'ta karşılaşılan gerçek hata).
  function extractText(message) {
    if (!message) return null;
    // Ephemeral/view-once gibi sarmalayıcıları aç
    const unwrapped =
      message.ephemeralMessage?.message ||
      message.viewOnceMessage?.message ||
      message.viewOnceMessageV2?.message ||
      message.documentWithCaptionMessage?.message ||
      message;

    return (
      unwrapped.conversation ||
      unwrapped.extendedTextMessage?.text ||
      unwrapped.imageMessage?.caption ||
      unwrapped.videoMessage?.caption ||
      unwrapped.documentMessage?.caption ||
      unwrapped.buttonsResponseMessage?.selectedButtonId ||
      unwrapped.listResponseMessage?.title ||
      unwrapped.reactionMessage?.text ||
      null
    );
  }

  function describeMessageType(message) {
    if (!message) return 'unknown';
    const keys = Object.keys(message);
    return keys.length ? keys.join(',') : 'empty';
  }

  // POC doğrulaması: gelen her mesajı hem konsola hem log dosyasına yaz.
  sock.ev.on('messages.upsert', ({ messages, type }) => {
    if (type !== 'notify') return;
    for (const msg of messages) {
      if (!msg.message) continue;
      const from = msg.key.remoteJid;
      const isGroup = from?.endsWith('@g.us');
      const body = extractText(msg.message);
      const msgType = describeMessageType(msg.message);
      const sender = msg.pushName || from?.split('@')[0] || 'Bilinmeyen';

      const entry = {
        timestamp: new Date().toISOString(),
        from,
        isGroup,
        pushName: sender,
        body,
        msgType, // metin çıkmadıysa hangi alan(lar) doluydu, buradan görülür
      };

      const preview = body ? body.slice(0, 80) : `[metin yok — tip: ${msgType}]`;
      console.log(`[MESAJ] ${isGroup ? 'GRUP' : 'DM'} ${from} — ${sender}: ${preview}`);
      fs.appendFileSync(LOG_FILE, JSON.stringify(entry) + '\n', 'utf-8');

      // Metin çıkarılamadıysa ham mesaj yapısını da ayrı bir dosyaya yaz
      // (bir sonraki tip eşlemesi için referans).
      if (!body) {
        fs.appendFileSync(
          path.join(__dirname, 'poc_unhandled_messages.log'),
          JSON.stringify({ timestamp: entry.timestamp, from, message: msg.message }) + '\n',
          'utf-8'
        );
      }
    }
  });

  // POC doğrulaması: bağlı olduğunuz grupları listele (whapi_fetcher.fetch_groups'un eşdeğeri).
  sock.ev.on('connection.update', async (update) => {
    if (update.connection === 'open') {
      try {
        const groups = await sock.groupFetchAllParticipating();
        const groupList = Object.values(groups).map((g) => ({ id: g.id, subject: g.subject }));
        console.log(`\n[GRUPLAR] ${groupList.length} grup bulundu:`);
        groupList.slice(0, 10).forEach((g) => console.log(`  - ${g.subject} (${g.id})`));
        fs.writeFileSync(
          path.join(__dirname, 'poc_groups.json'),
          JSON.stringify(groupList, null, 2),
          'utf-8'
        );
      } catch (e) {
        console.error('[HATA] Grup listesi alınamadı:', e.message);
      }
    }
  });
}

connect().catch((e) => console.error('[FATAL]', e));
