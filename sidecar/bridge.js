// Baileys -> webhook_server.py köprüsü (Saga epic #43).
// connect.js'in POC'ta doğrulanmış bağlantı/mesaj-ayrıştırma mantığını
// kullanır, farkı: log dosyasına yazmak yerine her mesajı Whapi'nin
// convert_whapi_message() çıktısıyla AYNI alan adlarıyla paketleyip
// Python tarafındaki /baileys-webhook endpoint'ine POST eder.
//
// ASIL ÜRETIM NUMARASI İLE ÇALIŞTIRMAYIN — epic #44/#45 tamamlanana kadar
// sadece test/ikincil numarayla kullanın.
//
// Kullanım: node bridge.js
// Ortam değişkenleri:
//   WEBHOOK_URL  (varsayılan: http://localhost:8080/baileys-webhook)

const { default: makeWASocket, useMultiFileAuthState, DisconnectReason } = require('@whiskeysockets/baileys');
const qrcode = require('qrcode-terminal');
const QRCode = require('qrcode');
const pino = require('pino');
const path = require('path');
const fs = require('fs');

const WEBHOOK_URL = process.env.WEBHOOK_URL || 'http://localhost:8080/baileys-webhook';
const UNHANDLED_LOG = path.join(__dirname, 'bridge_unhandled_messages.log');
const RISK_EVENTS_LOG = path.join(__dirname, 'risk_events.log');

let groupsIntervalId = null;

// Saga epic #44 (baileys-risk-paritesi): Whapi'nin Safety Meter'ının yerini
// tutacak sidecar/risk_check.js'in ham veri kaynağı. JSON Lines formatı —
// her satır tek bir olay. Append-only, pruning bu görevde YOK (bkz. plan.md
// Kararlar #2) — risk_check.js zaman penceresine göre kendi filtreler.
function logRiskEvent(event) {
  try {
    fs.appendFileSync(RISK_EVENTS_LOG, JSON.stringify({ ...event, ts: new Date().toISOString() }) + '\n', 'utf-8');
  } catch (e) {
    // Risk logu ikincil bir gözlem aracı — yazılamazsa köprünün asıl işlevini
    // (mesaj iletimi) durdurmaz, sadece konsola bir uyarı düşer.
    console.error('[RISK-LOG HATA]', e.message);
  }
}

// connect.js'teki extractText/describeMessageType ile birebir aynı —
// POC'ta doğrulanmış mantık, kopyalandı (bilinçli: iki script birbirinden
// bağımsız çalışabilmeli, connect.js hâlâ tek başına bağlantı testi için var).
function extractText(message) {
  if (!message) return null;
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

// Baileys mesajını, Python tarafının convert_whapi_message() çıktısıyla
// AYNI şekle (id, body, timestamp, chat_id, chat_name, sender_name, from,
// type) dönüştürür — webhook_server.py._handle_baileys_event bu alanları
// birebir bekliyor (bkz. add_to_processing_queue).
function toWhapiShape(msg) {
  const from = msg.key.remoteJid;
  const isGroup = from?.endsWith('@g.us');
  const body = extractText(msg.message);
  if (!body) return null; // Metin çıkarılamayan mesajları (reaction, protokol vb.) gönderme

  const senderJid = msg.key.participant || (isGroup ? null : from);
  const senderName = msg.pushName || senderJid?.split('@')[0] || 'Bilinmeyen';
  const timestampSec = typeof msg.messageTimestamp === 'number'
    ? msg.messageTimestamp
    : Number(msg.messageTimestamp?.low ?? Math.floor(Date.now() / 1000));

  return {
    id: msg.key.id,
    body,
    timestamp: timestampSec,
    chat_id: from,
    chat_name: null, // Baileys bu event'te grup adını vermiyor; Python tarafı chat_groups.json'dan zenginleştirebilir
    sender_name: senderName,
    from: senderJid || from,
    type: 'text',
    is_processed: false,
    source: 'baileys',
  };
}

async function postToWebhook(messages) {
  try {
    const res = await fetch(WEBHOOK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages }),
    });
    if (!res.ok) {
      console.error(`[WEBHOOK HATA] ${res.status} ${res.statusText}`);
    } else {
      console.log(`[WEBHOOK OK] ${messages.length} mesaj gönderildi -> ${WEBHOOK_URL}`);
    }
  } catch (e) {
    console.error('[WEBHOOK BAGLANTI HATASI]', e.message, `(hedef: ${WEBHOOK_URL}, webhook_server.py çalışıyor mu?)`);
  }
}

// Atomic write helper: temp file + rename to prevent partial writes
function atomicWrite(filePath, content) {
  try {
    const tmpPath = filePath + '.tmp';
    fs.writeFileSync(tmpPath, content, 'utf-8');
    fs.renameSync(tmpPath, filePath);
  } catch (e) {
    // Error caught and logged but does not crash bridge.js main loop
    console.error(`[QR-WRITE ERROR] ${e.message}`);
  }
}

// Write QR state to shared file: {qr: "data:image/png;base64,...", generated_at: <epoch ms>}
function writeQrState(qr, filePath = path.join(__dirname, '..', 'data', 'baileys_qr.json')) {
  const content = JSON.stringify({
    qr: qr,
    generated_at: Date.now()
  });
  atomicWrite(filePath, content);
}

// Write authenticated state to shared file: {status: "authenticated"}
function writeAuthenticatedState(filePath = path.join(__dirname, '..', 'data', 'baileys_qr.json')) {
  const content = JSON.stringify({
    status: 'authenticated'
  });
  atomicWrite(filePath, content);
}

// Write groups state to shared file: {groups: [{"id": "...", "name": "..."}]}
// Transforms Baileys groupFetchAllParticipating() response ({jid: GroupMetadata})
// to stored format by extracting id and subject (→ name)
function writeGroupsState(groupsObject, filePath = path.join(__dirname, '..', 'data', 'baileys_groups.json')) {
  try {
    const groupsArray = Object.values(groupsObject).map(g => ({
      id: g.id,
      name: g.subject
    }));
    const content = JSON.stringify({
      groups: groupsArray
    });
    atomicWrite(filePath, content);
  } catch (e) {
    console.error('[GROUPS-WRITE ERROR]', e.message);
  }
}

async function bridge() {
  const { state, saveCreds } = await useMultiFileAuthState(path.join(__dirname, 'auth_info_baileys'));

  const sock = makeWASocket({
    auth: state,
    logger: pino({ level: 'warn' }),
    printQRInTerminal: false,
  });

  sock.ev.on('creds.update', saveCreds);

  sock.ev.on('connection.update', (update) => {
    const { connection, lastDisconnect, qr } = update;

    if (qr) {
      console.log('\n=== QR KODU ===\n');
      qrcode.generate(qr, { small: true });
      // Generate PNG data URI and write to shared file for panel
      QRCode.toDataURL(qr).then(dataUri => {
        writeQrState(dataUri);
      }).catch(e => {
        console.error('[QR-GENERATE ERROR]', e.message);
      });
    }

    if (connection === 'close') {
      const statusCode = lastDisconnect?.error?.output?.statusCode;
      logRiskEvent({ type: 'disconnect', statusCode: statusCode ?? null });

      if (statusCode === DisconnectReason.connectionReplaced) {
        // 440 = "conflict/replaced": WhatsApp bu oturumla ikinci bir bağlantı
        // gördü. Hemen yeniden bağlanmak (bridge() çağırmak) YENİ bir çakışma
        // yaratıp döngüye girer (bu, gerçek bir olayda karşılaşılan hata) —
        // bu yüzden burada YENİDEN BAĞLANMIYORUZ, kullanıcı elle karar versin.
        console.log('[BAGLANTI KAPANDI] statusCode=440 (conflict/replaced) — YENIDEN BAGLANMIYOR.');
        console.log('[UYARI] Bu oturumu kullanan başka bir bağlantı algılandı (aynı makinede eski bir process, ya da telefon tarafında WhatsApp Web açık olabilir).');
        console.log('[UYARI] Diğer bağlantıyı kapatıp scripti elle yeniden başlatın.');
        return;
      }

      const shouldReconnect = statusCode !== DisconnectReason.loggedOut;
      console.log(`[BAGLANTI KAPANDI] statusCode=${statusCode} yenidenBaglan=${shouldReconnect}`);
      if (shouldReconnect) {
        setTimeout(bridge, 2000); // Ani reconnect döngüsünü önlemek için kısa gecikme
      } else {
        console.log('[OTURUM KAPANDI] auth_info_baileys/ klasörünü silip yeniden QR taratmanız gerekir.');
      }
    } else if (connection === 'open') {
      console.log(`[BAGLANDI] Köprü aktif. Mesajlar -> ${WEBHOOK_URL}`);
      writeAuthenticatedState();
      // Periyodik grup tarama (60 saniyede bir)
      if (groupsIntervalId) {
        clearInterval(groupsIntervalId);
      }
      groupsIntervalId = setInterval(() => {
        sock.groupFetchAllParticipating().then(groups => {
          writeGroupsState(groups);
        }).catch(e => {
          console.error('[GROUPS-FETCH ERROR]', e.message);
        });
      }, 60000);
    }
  });

  sock.ev.on('messages.upsert', async ({ messages, type }) => {
    if (type !== 'notify') return;

    const converted = [];
    for (const msg of messages) {
      if (!msg.message) continue;
      const shaped = toWhapiShape(msg);
      if (shaped) {
        converted.push(shaped);
      } else {
        fs.appendFileSync(
          UNHANDLED_LOG,
          JSON.stringify({ timestamp: new Date().toISOString(), key: msg.key, message: msg.message }) + '\n',
          'utf-8'
        );
      }
    }

    if (converted.length > 0) {
      logRiskEvent({ type: 'message', count: converted.length });
      await postToWebhook(converted);
    }
  });
}

module.exports = {
  writeQrState,
  writeAuthenticatedState,
  writeGroupsState
};

if (require.main === module) {
  bridge().catch((e) => console.error('[FATAL]', e));
}
