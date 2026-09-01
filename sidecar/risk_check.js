// Baileys risk göstergesi (Saga epic #44, task #351 — atdd.md).
//
// Whapi.cloud'un Safety Meter'ının (riskOfBlocking) DOĞRUDAN karşılığı
// DEĞİLDİR — WhatsApp resmi bir ban-risk skoru açıklamıyor. Bu araç sadece
// bridge.js'in gözlemlediği sinyalleri (disconnect sıklığı/tipi, mesaj
// hacmi) özetler. "Kesin doğru" değil, "mevcut sinyallerden en iyi tahmin".
//
// Kullanım: node risk_check.js
// Veri kaynağı: sidecar/risk_events.log (bridge.js tarafından üretilir)

const fs = require('fs');
const path = require('path');

const LOG_FILE = path.join(__dirname, 'risk_events.log');

const ONE_HOUR_MS = 60 * 60 * 1000;
const SEVEN_DAYS_MS = 7 * 24 * ONE_HOUR_MS;
const HIGH_RISK_DISCONNECT_COUNT_1H = 5; // atdd.md AC-3
const MIN_DATA_AGE_MS = ONE_HOUR_MS; // atdd.md AC-2: <1 saatlik veri "yetersiz"

// Session sağlığına dair sinyal veren statusCode'lar (epic #43'te
// karşılaşılanlar): 401=loggedOut, 440=conflict/replaced, 515=restart required.
const UNHEALTHY_STATUS_CODES = new Set([401, 440, 515]);

function readEvents() {
  if (!fs.existsSync(LOG_FILE)) {
    return null; // AC-5: veri kaynağı hiç yok
  }
  const raw = fs.readFileSync(LOG_FILE, 'utf-8');
  const lines = raw.split('\n').filter((l) => l.trim());
  const events = [];
  for (const line of lines) {
    try {
      const ev = JSON.parse(line);
      ev._tsMs = Date.parse(ev.ts);
      events.push(ev);
    } catch {
      // Bozuk/yarım yazılmış bir satır — atla, tüm dosyayı geçersiz kılma.
    }
  }
  return events;
}

function computeRisk(events, now = Date.now()) {
  if (events === null) {
    return {
      level: 'ERROR',
      message: 'Veri kaynağı bulunamadı — önce sidecar/bridge.js\'i çalıştırın.',
    };
  }

  if (events.length === 0) {
    return {
      level: 'UNKNOWN',
      message: 'Henüz hiçbir olay kaydedilmedi. bridge.js\'i biraz daha çalıştırıp tekrar deneyin.',
    };
  }

  const oldestEventMs = Math.min(...events.map((e) => e._tsMs));
  const dataAgeMs = now - oldestEventMs;

  const disconnectsLast1h = events.filter(
    (e) => e.type === 'disconnect' && now - e._tsMs <= ONE_HOUR_MS
  );
  const unhealthyDisconnectsLast1h = disconnectsLast1h.filter((e) =>
    UNHEALTHY_STATUS_CODES.has(e.statusCode)
  );
  const disconnectsLast7d = events.filter(
    (e) => e.type === 'disconnect' && now - e._tsMs <= SEVEN_DAYS_MS
  );
  const messageEvents = events.filter((e) => e.type === 'message');
  const messagesLast1h = messageEvents
    .filter((e) => now - e._tsMs <= ONE_HOUR_MS)
    .reduce((sum, e) => sum + (e.count || 0), 0);

  const hasMessageData = messageEvents.length > 0;
  const hasDisconnectData = events.some((e) => e.type === 'disconnect');

  // AC-2: veri henüz çok yeni (<1 saat) — güvenli/güvensiz diye YANLIŞ
  // bir sonuç vermek yerine açıkça "bilinmiyor" de.
  if (dataAgeMs < MIN_DATA_AGE_MS) {
    return {
      level: 'UNKNOWN',
      message: `Veri henüz toplanıyor (${Math.round(dataAgeMs / 60000)} dakikalık veri var, en az 60 dakika gerekiyor). Daha sonra tekrar deneyin.`,
      disconnectsLast1h: unhealthyDisconnectsLast1h.length,
      messagesLast1h,
    };
  }

  // AC-3: sık disconnect -> High risk (pazarlıksız, kısmi veri olsa bile
  // disconnect verisi varsa bu kontrol önce yapılır).
  if (unhealthyDisconnectsLast1h.length >= HIGH_RISK_DISCONNECT_COUNT_1H) {
    return {
      level: 'HIGH',
      message: `Son 1 saatte ${unhealthyDisconnectsLast1h.length} kez session sorunu (401/440/515) — işlemleri durdurup session'ı gözden geçirin.`,
      disconnectsLast1h: unhealthyDisconnectsLast1h.length,
      disconnectsLast7d: disconnectsLast7d.length,
      messagesLast1h,
    };
  }

  // AC-4: kısmi veri — disconnect verisi var ama mesaj verisi hiç yoksa
  // (veya tersi), bunu açıkça belirt, sessizce "0/güvenli" sayma.
  if (hasDisconnectData && !hasMessageData) {
    return {
      level: 'MEDIUM',
      message: 'KISMİ VERİ: bağlantı sağlığı ölçülebildi ama mesaj hacmi hiç kaydedilmedi (henüz mesaj gelmemiş olabilir).',
      disconnectsLast1h: unhealthyDisconnectsLast1h.length,
      disconnectsLast7d: disconnectsLast7d.length,
      messagesLast1h: null,
    };
  }

  // AC-1: happy path.
  return {
    level: 'LOW',
    message: `Son 7 günde ${disconnectsLast7d.length} disconnect, hesap stabil görünüyor.`,
    disconnectsLast1h: unhealthyDisconnectsLast1h.length,
    disconnectsLast7d: disconnectsLast7d.length,
    messagesLast1h,
  };
}

function printReport(result) {
  const icons = { LOW: '✅', MEDIUM: '🟡', HIGH: '🔴', UNKNOWN: '❓', ERROR: '❌' };
  console.log('='.repeat(60));
  console.log('  BAILEYS RİSK GÖSTERGESİ (Whapi Safety Meter DEĞİL — proxy sinyal)');
  console.log('='.repeat(60));
  console.log(`${icons[result.level] || ''} Risk: ${result.level}`);
  console.log(result.message);
  if (result.disconnectsLast1h !== undefined) {
    console.log(`\nSon 1 saat sorunlu disconnect: ${result.disconnectsLast1h}`);
  }
  if (result.disconnectsLast7d !== undefined) {
    console.log(`Son 7 gün toplam disconnect: ${result.disconnectsLast7d}`);
  }
  if (result.messagesLast1h !== undefined && result.messagesLast1h !== null) {
    console.log(`Son 1 saat işlenen mesaj: ${result.messagesLast1h}`);
  }
  console.log('='.repeat(60));
}

// Modül olarak da import edilebilir olsun diye (unit test) export ediyoruz;
// doğrudan `node risk_check.js` ile çalıştırılınca CLI çıktısı basılır.
module.exports = { computeRisk, readEvents };

if (require.main === module) {
  const events = readEvents();
  const result = computeRisk(events);
  printReport(result);
}
