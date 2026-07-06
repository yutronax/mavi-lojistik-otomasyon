# -*- coding: utf-8 -*-
"""
admin_panel.py

Mobil Yönetim Paneli (Flask Web App)
VPS üzerinde PM2 ile çalışır; telefon tarayıcısından erişilir.

Özellikler:
  - Şifreli giriş (ADMIN_PANEL_PASSWORD, .env'den)
  - Servis durumu + sistem metrikleri (CPU/RAM/Disk)
  - Servis Başlat / Durdur / Yeniden Başlat (PM2)
  - Canlı log görüntüleme (pm2_out.log + vps_runtime.log)
  - Kara liste yönetimi (data/blacklist.json — ekle/sil/ara)
  - Ayar düzenleme (.env içindeki seçili anahtarlar)

Çalıştırma: ./.venv/bin/python3 src/api/admin_panel.py  (PM2: mavi-admin-panel)
"""

import os
import sys
import json
import time
import shutil
import secrets
import logging
import subprocess
import threading
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, Response

# Proje kök dizini (src/api/admin_panel.py → 2 üst klasör)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"), override=True)

SERVICE_NAME = "mavi-lojistik-server"
BLACKLIST_PATH = os.path.join(PROJECT_ROOT, "data", "blacklist.json")
GROUPS_PATH = os.path.join(PROJECT_ROOT, "data", "chat_groups.json")
MESSAGES_PATH = os.path.join(PROJECT_ROOT, "data", "live_messages.json")
UNPROCESSED_PATH = os.path.join(PROJECT_ROOT, "data", "onaylanmamis_ayristirilmis.json")
APPROVED_PATH = os.path.join(PROJECT_ROOT, "data", "Onaylananlar.json")
IL_ILCE_PATH = os.path.join(PROJECT_ROOT, "data", "il_ilçe_mahalle.json")
ARAC_KASA_PATH = os.path.join(PROJECT_ROOT, "data", "arac_yuk_kasa_tipleri.json")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
LOG_PATHS = [
    "/root/.pm2/logs/mavi-lojistik-server-out.log",
    "/root/.pm2/logs/mavi-admin-panel-out.log",
    os.path.join(PROJECT_ROOT, "logs", "vps_runtime.log"),
]

# Panelden düzenlenebilen .env anahtarları (güvenlik: API key'ler dahil DEĞİL)
EDITABLE_ENV_KEYS = [
    "FETCH_HOURS_BACK",
    "DUPLICATE_CHECK_HOURS",
    "DEFAULT_UI_FILTER_MINUTES",
    "WHATSAPP_POLL_INTERVAL",
    "START_HOUR",
    "END_HOUR",
    "AUTO_SUBMIT",
    "BATCH_SLEEP_TIME",
    "LOOP_WAIT_TIME",
]

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AdminPanel")

# YukBurada submission entegrasyonu
try:
    from tools.submit_approved_loads import YukBuradaSubmitter
    from src.services.submission_queue import SubmissionQueue
    _yukburada_submitter = YukBuradaSubmitter()
    _submission_queue = SubmissionQueue(_yukburada_submitter)
    _submission_queue.start()
    logger.info("YukBurada submission queue başlatıldı.")
except Exception as _e:
    logger.warning(f"YukBurada entegrasyonu başlatılamadı: {_e}")
    _yukburada_submitter = None
    _submission_queue = None

app = Flask(__name__)

# Bellek içi oturum tokenları: {token: expiry_epoch}
TOKENS = {}
TOKEN_TTL = 7 * 24 * 3600  # 7 gün
# Başarısız giriş takibi: {ip: [timestamps]}
FAILED_LOGINS = {}
MAX_FAILED = 5
FAIL_WINDOW = 30  # 10 dakika


def _get_password():
    """Panel şifresini .env'den okur; tanımsızsa None döner (giriş kapalı)."""
    return os.getenv("ADMIN_PANEL_PASSWORD")


def _check_rate_limit(ip):
    """IP başına başarısız giriş limitini kontrol eder; aşıldıysa False."""
    now = time.time()
    attempts = [t for t in FAILED_LOGINS.get(ip, []) if now - t < FAIL_WINDOW]
    FAILED_LOGINS[ip] = attempts
    return len(attempts) < MAX_FAILED


def require_auth(f):
    """API endpoint'lerini Bearer token ile korur."""
    @wraps(f)
    def wrapper(*args, **kwargs):
        """Authorization header'daki tokenı doğrular, geçersizse 401 döner."""
        auth = request.headers.get("Authorization", "")
        token = auth[7:] if auth.startswith("Bearer ") else None
        if not token or token not in TOKENS or TOKENS[token] < time.time():
            return jsonify({"error": "Yetkisiz"}), 401
        return f(*args, **kwargs)
    return wrapper


def _pm2(args):
    """PM2 komutu çalıştırır, (success, output) döner."""
    try:
        p = subprocess.run(["pm2"] + args, capture_output=True, text=True, timeout=30)
        return p.returncode == 0, p.stdout or p.stderr
    except Exception as e:
        return False, str(e)


def _atomic_write(path, content):
    """Dosyayı geçici dosya + rename ile atomik yazar (yarım yazma koruması)."""
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(content)
    os.replace(tmp, path)


# ---------------- API: Giriş ----------------

@app.route("/api/login", methods=["POST"])
def login():
    """Şifre doğrulayıp 7 günlük oturum tokenı verir; brute-force korumalı."""
    ip = request.remote_addr or "?"
    if not _check_rate_limit(ip):
        return jsonify({"error": "Çok fazla deneme. 10 dk bekleyin."}), 429
    pwd = _get_password()
    if not pwd:
        return jsonify({"error": "Panel şifresi sunucuda tanımlı değil (.env ADMIN_PANEL_PASSWORD)"}), 500
    body = request.get_json(silent=True) or {}
    if not secrets.compare_digest(str(body.get("password", "")), pwd):
        FAILED_LOGINS.setdefault(ip, []).append(time.time())
        return jsonify({"error": "Hatalı şifre"}), 401
    token = secrets.token_hex(32)
    TOKENS[token] = time.time() + TOKEN_TTL
    return jsonify({"token": token})


# ---------------- API: Durum ----------------

_status_cache = {"service": {"status": "unknown", "cpu": 0, "memory": 0, "restarts": 0, "uptime": 0}, "system": None}

def _refresh_status_cache():
    """PM2 jlist'i arka planda 8 sn'de bir çalıştırıp cache'ler."""
    def _loop():
        global _status_cache
        while True:
            result = {"service": {"status": "unknown", "cpu": 0, "memory": 0, "restarts": 0, "uptime": 0}}
            ok, out = _pm2(["jlist"])
            if ok and out.strip():
                try:
                    data = json.loads(out[out.find("["):])
                    for a in data:
                        if a.get("name") == SERVICE_NAME:
                            env = a.get("pm2_env", {})
                            result["service"] = {
                                "status": env.get("status", "unknown"),
                                "cpu": a.get("monit", {}).get("cpu", 0),
                                "memory": round(a.get("monit", {}).get("memory", 0) / 1048576, 1),
                                "restarts": env.get("restart_time", 0),
                                "uptime": env.get("pm_uptime", 0),
                            }
                except Exception as e:
                    logger.error(f"jlist parse: {e}")
            try:
                mem = {}
                with open("/proc/meminfo") as f:
                    for line in f:
                        k, v = line.split(":", 1)
                        mem[k] = int(v.strip().split()[0])
                total, avail = mem.get("MemTotal", 1), mem.get("MemAvailable", 0)
                du = shutil.disk_usage("/")
                result["system"] = {
                    "ram_pct": round((total - avail) / total * 100, 1),
                    "ram_used_mb": round((total - avail) / 1024),
                    "ram_total_mb": round(total / 1024),
                    "disk_pct": round(du.used / du.total * 100, 1),
                    "load": round(os.getloadavg()[0], 2),
                }
            except Exception:
                result["system"] = None
            _status_cache = result
            time.sleep(8)
    t = threading.Thread(target=_loop, daemon=True, name="status-poller")
    t.start()

@app.route("/api/status")
@require_auth
def status():
    """Cache'lenmiş PM2 durumunu döner — disk/subprocess yok."""
    return jsonify(_status_cache)




# ---------------- API: Servis Kontrol ----------------

@app.route("/api/service/<action>", methods=["POST"])
@require_auth
def service_action(action):
    """Servisi başlatır/durdurur/yeniden başlatır (PM2 üzerinden)."""
    if action == "start":
        ok, out = _pm2(["start", os.path.join(PROJECT_ROOT, "ecosystem.config.js"), "--only", SERVICE_NAME])
    elif action == "stop":
        ok, out = _pm2(["stop", SERVICE_NAME])
    elif action == "restart":
        ok, out = _pm2(["restart", SERVICE_NAME])
    else:
        return jsonify({"error": "Geçersiz işlem"}), 400
    logger.info(f"Servis işlemi: {action} → {'OK' if ok else 'HATA'}")
    return jsonify({"ok": ok, "output": out[-500:]})


# ---------------- API: Loglar ----------------

@app.route("/api/logs")
@require_auth
def logs():
    """Log dosyalarının son N satırını birleştirip döner."""
    lines = min(int(request.args.get("lines", 100)), 500)
    chunks = []
    _noise = {
        "Serving Flask app", "Debug mode:", "WARNING: This is a development",
        "Use a production WSGI", "Press CTRL+C", " * Running on",
        " * Restarting with", " * Debugger is",
    }
    for path in LOG_PATHS:
        if os.path.exists(path):
            try:
                result = subprocess.run(
                    ["tail", "-n", str(lines), path],
                    capture_output=True, text=True, timeout=10, errors="replace"
                )
                filtered = [
                    l for l in result.stdout.splitlines()
                    if not any(n in l for n in _noise)
                ]
                if filtered:
                    chunks.append(f"━━━ {os.path.basename(path)} ━━━")
                    chunks.append("\n".join(filtered))
            except Exception as e:
                chunks.append(f"{path} okunamadı: {e}")
    return jsonify({"logs": "\n".join(chunks) or "Log bulunamadı."})



# ---------------- API: Mesajlar ----------------

@app.route("/api/messages", methods=["GET"])
@require_auth
def messages_get():
    """Son WhatsApp mesajlarını (data/live_messages.json) en yeniden eskiye döner.

    ?minutes= : Operasyon Merkezi'ndeki (Flet) zaman filtresiyle aynı seçenekler
    (10 / 60 / 1440 / all) — sadece o pencere içindeki mesajları döner.
    """
    limit = min(int(request.args.get("limit", 50)), 200)
    minutes = request.args.get("minutes", "all")
    try:
        with open(MESSAGES_PATH, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        items = []
    if minutes != "all":
        try:
            cutoff = time.time() - int(minutes) * 60
            items = [m for m in items if m.get("timestamp", 0) >= cutoff]
        except ValueError:
            pass
    items = sorted(items, key=lambda m: m.get("timestamp", 0), reverse=True)
    return jsonify({"messages": items[:limit]})


# ---------------- API: Ayrıştırılmış Mesajlar (Operasyon Merkezi) ----------------

_unprocessed_cache = []
_unprocessed_lock = threading.Lock()

def _load_unprocessed():
    """Her zaman bellekten döner — disk okuma yok."""
    with _unprocessed_lock:
        return list(_unprocessed_cache)

def _save_unprocessed(items):
    global _unprocessed_cache
    _atomic_write(UNPROCESSED_PATH, json.dumps(items, ensure_ascii=False, indent=2))
    with _unprocessed_lock:
        _unprocessed_cache = items

def _start_bg_loader():
    """Arka planda dosyayı 5 sn'de bir kontrol edip cache'i günceller."""
    def _loop():
        global _unprocessed_cache
        last_mtime = 0.0
        while True:
            try:
                mtime = os.path.getmtime(UNPROCESSED_PATH)
                if mtime != last_mtime:
                    with open(UNPROCESSED_PATH, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    with _unprocessed_lock:
                        _unprocessed_cache = data
                    last_mtime = mtime
            except Exception:
                pass
            time.sleep(5)
    t = threading.Thread(target=_loop, daemon=True, name="unprocessed-loader")
    t.start()


CLEANUP_DAYS = 2  # Bu kadar günden eski kayıtlar silinir

def _cleanup_old_unprocessed():
    """CLEANUP_DAYS günden eski ayrıştırılmış mesajları siler."""
    try:
        items = _load_unprocessed()
        cutoff = time.time() - CLEANUP_DAYS * 86400
        before = len(items)
        items = [
            m for m in items
            if (m.get("createdAt") or m.get("message_timestamp") or 0) >= cutoff
        ]
        after = len(items)
        if before != after:
            _save_unprocessed(items)
            logging.info(f"[CLEANUP] {before - after} eski mesaj silindi ({CLEANUP_DAYS} günden eski). Kalan: {after}")
        else:
            logging.info(f"[CLEANUP] Silinecek eski mesaj yok. Toplam: {after}")
    except Exception as e:
        logging.error(f"[CLEANUP] Hata: {e}")

def _schedule_daily_cleanup():
    """Her gece 00:00'da cleanup çalıştıran arka plan thread'i."""
    def _loop():
        while True:
            now = datetime.now()
            next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            wait_secs = (next_midnight - now).total_seconds()
            time.sleep(wait_secs)
            _cleanup_old_unprocessed()
    t = threading.Thread(target=_loop, daemon=True, name="daily-cleanup")
    t.start()
    logging.info(f"[CLEANUP] Günlük temizlik planlandı — her gece 00:00 ({CLEANUP_DAYS} günden eskiler silinir)")

def _slim_msg(m):
    """Gereksiz büyük alanları (participants vb.) çıkararak hafif kopya döner."""
    info = m.get("message_info") or {}
    return {
        "message_id": m.get("message_id", ""),
        "createdAt": m.get("createdAt") or m.get("message_timestamp") or 0,
        "shipments": m.get("shipments", []),
        "message_info": {
            "body": info.get("body", ""),
            "sender": info.get("sender", ""),
            "sender_number": info.get("sender_number", ""),
            "timestamp": info.get("timestamp", 0),
            "chat_name": info.get("chat_name") or info.get("chat_id", ""),
        },
    }

@app.route("/api/unprocessed", methods=["GET"])
@require_auth
def unprocessed_get():
    """Ayrıştırılmış ama onaylanmamış mesajları döner. Boş içerikli mesajlar hariç."""
    minutes = request.args.get("minutes", "all")
    items = _load_unprocessed()
    # Boş body ve sevkiyatsız mesajları filtrele
    items = [
        m for m in items
        if (m.get("message_info") or {}).get("body", "").strip()
        and m.get("shipments")
    ]
    if minutes != "all":
        try:
            cutoff = time.time() - int(minutes) * 60
            items = [m for m in items if (m.get("createdAt") or m.get("message_timestamp") or 0) >= cutoff]
        except ValueError:
            pass
    items = sorted(items, key=lambda m: m.get("createdAt") or m.get("message_timestamp") or 0, reverse=True)
    return jsonify({"messages": [_slim_msg(m) for m in items]})

@app.route("/api/unprocessed/<msg_id>/approve/<int:ship_idx>", methods=["POST"])
@require_auth
def unprocessed_approve(msg_id, ship_idx):
    """Sevkiyatı onaylar: YukBurada'ya gönderir + Onaylananlar.json'a ekler + listeden çıkarır."""
    items = _load_unprocessed()
    msg = next((m for m in items if m.get("message_id") == msg_id), None)
    if not msg:
        return jsonify({"error": "Mesaj bulunamadı"}), 404
    shipments = msg.get("shipments", [])
    if ship_idx >= len(shipments):
        return jsonify({"error": "Sevkiyat bulunamadı"}), 404
    shipment = shipments[ship_idx]
    # Lokasyon kontrolü — boş il ile YükBurada'ya gitmesin
    nereden = (shipment.get("nereden_il") or "").strip()
    nereye  = (shipment.get("nereye_il")  or "").strip()
    if not nereden or not nereye:
        return jsonify({"error": f"Lokasyon eksik: nereden='{nereden}' nereye='{nereye}' — önce düzenle"}), 400
    shipments.pop(ship_idx)
    shipment["onay_tarihi"] = time.strftime("%Y-%m-%d %H:%M:%S")
    shipment["message_id"] = msg_id

    # Masaüstü uygulamasıyla aynı: araç/kasa kombinasyonları üret ve kuyruğa ekle
    def _parse_list(v):
        return v if isinstance(v, list) else ([v] if v else [])
    at = _parse_list(shipment.get("arac_tipi", []))
    kt = _parse_list(shipment.get("kasa_tipi", []))
    if not at and not kt:
        combos = [""]
    elif not at:
        combos = kt
    elif not kt:
        combos = at
    else:
        combos = [f"{a}-{k}" for a in at for k in kt]
    shipment["arac_kasa_kombinasyon_listesi"] = combos

    if _submission_queue is not None:
        _submission_queue.add_task(shipment)
        logger.info(f"[APPROVE] {msg_id}[{ship_idx}] YukBurada kuyruğuna eklendi.")
    else:
        logger.warning(f"[APPROVE] YukBurada entegrasyonu yok — sadece Onaylananlar.json'a kaydedildi.")

    # Onaylananlar.json'a ekle
    try:
        with open(APPROVED_PATH, "r", encoding="utf-8") as f:
            approved = json.load(f)
    except Exception:
        approved = []
    approved.append(shipment)
    _atomic_write(APPROVED_PATH, json.dumps(approved, ensure_ascii=False, indent=2))

    # Mesajda sevkiyat kalmadıysa listeden çıkar
    if not shipments:
        items = [m for m in items if m.get("message_id") != msg_id]
    _save_unprocessed(items)
    return jsonify({"ok": True})

_approve_lock = threading.Lock()

def _approve_message(msg_id):
    """Mesajdaki tüm sevkiyatları onaylar ve YukBurada kuyruğuna ekler.
    Döner: (count, error_str)."""
    with _approve_lock:
        items = _load_unprocessed()
        msg = next((m for m in items if m.get("message_id") == msg_id), None)
        if not msg:
            return 0, "Mesaj bulunamadı"
        shipments = msg.get("shipments", [])
        if not shipments:
            # Sevkiyatsız mesajı listeden temizle
            items = [m for m in items if m.get("message_id") != msg_id]
            _save_unprocessed(items)
            return 0, "Sevkiyat yok"

        def _parse_list(v):
            return v if isinstance(v, list) else ([v] if v else [])

        try:
            with open(APPROVED_PATH, "r", encoding="utf-8") as f:
                approved = json.load(f)
        except Exception:
            approved = []

        for shipment in shipments:
            shipment = shipment.copy()
            shipment["onay_tarihi"] = time.strftime("%Y-%m-%d %H:%M:%S")
            shipment["message_id"] = msg_id
            at = _parse_list(shipment.get("arac_tipi", []))
            kt = _parse_list(shipment.get("kasa_tipi", []))
            combos = at or kt or [""]
            shipment["arac_kasa_kombinasyon_listesi"] = combos
            if _submission_queue is not None:
                _submission_queue.add_task(shipment)
            approved.append(shipment)

        _atomic_write(APPROVED_PATH, json.dumps(approved, ensure_ascii=False, indent=2))
        items = [m for m in items if m.get("message_id") != msg_id]
        _save_unprocessed(items)
        logger.info(f"[APPROVE_ALL] {msg_id}: {len(shipments)} sevkiyat onaylandı.")
        return len(shipments), None


@app.route("/api/unprocessed/<msg_id>/approve_all", methods=["POST"])
@require_auth
def unprocessed_approve_all(msg_id):
    """Mesajdaki tüm sevkiyatları onaylar ve YukBurada'ya gönderir."""
    count, err = _approve_message(msg_id)
    if err:
        return jsonify({"error": err}), 404
    return jsonify({"ok": True, "count": count})


# ---------------- Sunucu Tarafı Oto Onay ----------------
AUTO_APPROVE_STATE_PATH = os.path.join(PROJECT_ROOT, "data", "auto_approve_state.json")
_auto_approve_enabled = True

def _load_auto_state():
    global _auto_approve_enabled
    try:
        with open(AUTO_APPROVE_STATE_PATH, "r", encoding="utf-8") as f:
            _auto_approve_enabled = bool(json.load(f).get("enabled", True))
    except Exception:
        _auto_approve_enabled = True

def _save_auto_state():
    try:
        _atomic_write(AUTO_APPROVE_STATE_PATH, json.dumps({"enabled": _auto_approve_enabled}))
    except Exception:
        pass

def _auto_approve_loop():
    """3 saniyede bir, son 1 saat içindeki en yeni mesajı otomatik onaylar."""
    while True:
        try:
            if _auto_approve_enabled:
                cutoff = time.time() - 3600  # son 1 saat
                items = _load_unprocessed()
                candidates = [
                    m for m in items
                    if m.get("shipments")
                    and (m.get("message_info") or {}).get("body", "").strip()
                    and (m.get("createdAt") or m.get("message_timestamp") or 0) >= cutoff
                ]
                if candidates:
                    candidates.sort(key=lambda m: m.get("createdAt") or m.get("message_timestamp") or 0, reverse=True)
                    mid = candidates[0].get("message_id")
                    count, err = _approve_message(mid)
                    if count:
                        logger.info(f"[AUTO_APPROVE] {mid}: {count} sevkiyat otomatik onaylandı.")
        except Exception as e:
            logger.error(f"[AUTO_APPROVE] hata: {e}")
        time.sleep(3)

def _start_auto_approve():
    _load_auto_state()
    t = threading.Thread(target=_auto_approve_loop, daemon=True, name="auto-approve")
    t.start()


@app.route("/api/auto-approve", methods=["GET"])
@require_auth
def auto_approve_get():
    return jsonify({"enabled": _auto_approve_enabled})


@app.route("/api/auto-approve", methods=["POST"])
@require_auth
def auto_approve_set():
    global _auto_approve_enabled
    data = request.get_json(force=True) or {}
    _auto_approve_enabled = bool(data.get("enabled"))
    _save_auto_state()
    logger.info(f"[AUTO_APPROVE] durum: {'ACIK' if _auto_approve_enabled else 'KAPALI'}")
    return jsonify({"ok": True, "enabled": _auto_approve_enabled})

@app.route("/api/unprocessed/<msg_id>/shipment/<int:ship_idx>", methods=["DELETE"])
@require_auth
def unprocessed_delete_shipment(msg_id, ship_idx):
    """Sevkiyatı siler (mesajı değil)."""
    items = _load_unprocessed()
    msg = next((m for m in items if m.get("message_id") == msg_id), None)
    if not msg:
        return jsonify({"error": "Mesaj bulunamadı"}), 404
    shipments = msg.get("shipments", [])
    if ship_idx >= len(shipments):
        return jsonify({"error": "Sevkiyat bulunamadı"}), 404
    shipments.pop(ship_idx)
    if not shipments:
        items = [m for m in items if m.get("message_id") != msg_id]
    _save_unprocessed(items)
    return jsonify({"ok": True})

@app.route("/api/unprocessed/<msg_id>", methods=["GET"])
@require_auth
def unprocessed_get_one(msg_id):
    """Tek mesajın tam body'sini döner."""
    items = _load_unprocessed()
    msg = next((m for m in items if m.get("message_id") == msg_id), None)
    if not msg:
        return jsonify({"error": "Mesaj bulunamadı"}), 404
    info = msg.get("message_info") or {}
    return jsonify({"body": info.get("body", "")})

@app.route("/api/unprocessed/<msg_id>", methods=["DELETE"])
@require_auth
def unprocessed_delete_msg(msg_id):
    """Tüm mesajı siler."""
    items = [m for m in _load_unprocessed() if m.get("message_id") != msg_id]
    _save_unprocessed(items)
    return jsonify({"ok": True})


# ---------------- API: Form Verileri (il/ilçe + araç/kasa/yük) ----------------

@app.route("/api/form-data", methods=["GET"])
@require_auth
def form_data():
    """Düzenleme formu için il/ilçe ve araç/kasa/yük listelerini döner."""
    try:
        with open(IL_ILCE_PATH, "r", encoding="utf-8") as f:
            il_ilce = json.load(f)
    except Exception:
        il_ilce = []
    try:
        with open(ARAC_KASA_PATH, "r", encoding="utf-8") as f:
            types = json.load(f)
    except Exception:
        types = {}
    # il_ilce: [{il, ilceler:[{ilce, mahalleler}]}] → sadece il + ilçe listesi gönder (mahalle gerekmez)
    slim = [{"il": item["il"], "ilceler": [i["ilce"] for i in item.get("ilceler", [])]} for item in il_ilce]
    return jsonify({"il_ilce": slim, "types": types})


@app.route("/api/unprocessed/<msg_id>/shipment/<int:ship_idx>", methods=["PATCH"])
@require_auth
def unprocessed_patch_shipment(msg_id, ship_idx):
    """Sevkiyat alanlarını günceller."""
    items = _load_unprocessed()
    msg = next((m for m in items if m.get("message_id") == msg_id), None)
    if not msg:
        return jsonify({"error": "Mesaj bulunamadi"}), 404
    shipments = msg.get("shipments", [])
    if ship_idx >= len(shipments):
        return jsonify({"error": "Sevkiyat bulunamadi"}), 404
    updates = request.get_json(force=True) or {}
    shipments[ship_idx].update(updates)
    _save_unprocessed(items)
    return jsonify({"ok": True, "shipment": shipments[ship_idx]})


# ---------------- API: Gönderilenler (YukBurada) ----------------

@app.route("/api/sent", methods=["GET"])
@require_auth
def sent_loads():
    """YukBurada API'sinden gönderilmiş ilanları çeker."""
    if _yukburada_submitter is None:
        return jsonify({"error": "YukBurada entegrasyonu aktif değil"}), 503
    try:
        loads = _yukburada_submitter.fetch_live_loads()
        return jsonify({"loads": loads, "count": len(loads)})
    except Exception as e:
        logger.error(f"[SENT] fetch_live_loads hatası: {e}")
        return jsonify({"error": str(e)}), 500


# ---------------- API: Grup Yönetimi ----------------

def _load_groups():
    """chat_groups.json listesini okur."""
    try:
        with open(GROUPS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

@app.route("/api/groups", methods=["GET"])
@require_auth
def groups_get():
    """Kayıtlı WhatsApp gruplarını döner."""
    return jsonify({"groups": _load_groups()})

@app.route("/api/whatsapp-health", methods=["GET"])
@require_auth
def whatsapp_health():
    """Whapi kanal sağlık durumunu döner."""
    import urllib.request, urllib.error
    token = os.getenv("WHATSAPP_TOKEN", "").strip()
    if not token:
        return jsonify({"status": "error", "detail": "Token yok"})
    try:
        req = urllib.request.Request(
            "https://gate.whapi.cloud/health",
            headers={"Authorization": f"Bearer {token}", "User-Agent": "curl/7.88.1"},
        )
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        # Whapi health: {"status":"ok"/"error", "channel":{"status":"active"/"inactive",...}}
        # Whapi health: {"status": {"code": 4, "text": "AUTH"}, "user": {...}}
        st_obj = data.get("status", {})
        code = st_obj.get("code", 0) if isinstance(st_obj, dict) else 0
        text = str(st_obj.get("text", st_obj) if isinstance(st_obj, dict) else st_obj)
        user = data.get("user", {})
        pushname = user.get("pushname", "") if isinstance(user, dict) else ""
        phone = user.get("id", "") if isinstance(user, dict) else ""
        # code 4 = AUTH (aktif bağlı), diğerleri sorunlu
        healthy = code == 4
        detail = f"{text} — {pushname} ({phone})" if healthy and pushname else text
        return jsonify({"status": "ok" if healthy else "error", "detail": detail})
    except urllib.error.HTTPError as e:
        return jsonify({"status": "error", "detail": f"HTTP {e.code}"})
    except Exception as e:
        return jsonify({"status": "error", "detail": str(e)})


_grp_cache: dict = {"ts": 0, "groups": []}  # Whapi yanıtı 30s önbelleklenir

@app.route("/api/groups/available", methods=["GET"])
@require_auth
def groups_available():
    """Whapi'dan tüm grupları çekip kayıtlı olanları işaretler. Sonuç 30s önbelleklenir."""
    import urllib.request, urllib.error, time
    force = request.args.get("force") == "1"
    now = time.time()
    if not force and now - _grp_cache["ts"] < 30 and _grp_cache["groups"]:
        all_groups = _grp_cache["groups"]
    else:
        token = os.getenv("WHATSAPP_TOKEN", "").strip()
        if not token:
            env_path = os.path.join(PROJECT_ROOT, ".env")
            env_exists = os.path.exists(env_path)
            return jsonify({"error": f"WHATSAPP_TOKEN okunamadi. .env yolu: {env_path} (mevcut: {env_exists})"}), 500
        try:
            req = urllib.request.Request(
                "https://gate.whapi.cloud/groups?count=100",
                headers={
                    "Authorization": f"Bearer {token}",
                    "User-Agent": "curl/7.88.1",
                    "Accept": "application/json",
                }
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode())
            all_groups = data.get("groups", [])
            _grp_cache["groups"] = all_groups
            _grp_cache["ts"] = now
        except urllib.error.HTTPError as e:
            if e.code == 403:
                return jsonify({"error": f"Whapi token geçersiz veya süresi dolmuş (403). app.whapi.cloud panelinden token'ı kontrol edin ve VPS .env dosyasını güncelleyin."}), 500
            return jsonify({"error": f"Whapi HTTP hatası: {e.code} {e.reason}"}), 500
        except Exception as e:
            return jsonify({"error": f"Whapi bağlantı hatası: {e}"}), 500
    saved_ids = {g["id"] for g in _load_groups()}
    result = [{"id": g["id"], "name": g.get("name",""), "saved": g["id"] in saved_ids}
              for g in all_groups if g.get("type") == "group"]
    result.sort(key=lambda x: (x["saved"], x["name"]))  # kayıtlı olmayanlar önce
    cached = not force and now - _grp_cache["ts"] < 30
    return jsonify({"groups": result, "cached": cached})

@app.route("/api/groups", methods=["POST"])
@require_auth
def groups_add():
    """Gruba ekler (id + name)."""
    body = request.get_json(silent=True) or {}
    gid = str(body.get("id", "")).strip()
    name = str(body.get("name", "")).strip()
    if not gid or not name:
        return jsonify({"error": "id ve name gerekli"}), 400
    groups = _load_groups()
    if any(g["id"] == gid for g in groups):
        return jsonify({"ok": True, "msg": "Zaten kayıtlı"})
    groups.append({"name": name, "id": gid})
    _atomic_write(GROUPS_PATH, json.dumps(groups, ensure_ascii=False, indent=2))
    logger.info(f"Grup eklendi: {name} ({gid})")
    return jsonify({"ok": True})

@app.route("/api/groups/<path:group_id>", methods=["DELETE"])
@require_auth
def groups_remove(group_id):
    """Grubu listeden çıkarır."""
    groups = _load_groups()
    new_groups = [g for g in groups if g["id"] != group_id]
    if len(new_groups) == len(groups):
        return jsonify({"error": "Grup bulunamadı"}), 404
    _atomic_write(GROUPS_PATH, json.dumps(new_groups, ensure_ascii=False, indent=2))
    logger.info(f"Grup silindi: {group_id}")
    return jsonify({"ok": True})

# ---------------- API: Kara Liste ----------------

def _load_blacklist():
    """blacklist.json'u liste olarak okur; yoksa boş liste."""
    try:
        with open(BLACKLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


@app.route("/api/blacklist", methods=["GET"])
@require_auth
def blacklist_get():
    """Kara listeyi döner (opsiyonel ?q= araması ile)."""
    items = _load_blacklist()
    q = request.args.get("q", "").strip()
    if q:
        items = [n for n in items if q in n]
    return jsonify({"count": len(_load_blacklist()), "items": items[:200]})


@app.route("/api/blacklist", methods=["POST"])
@require_auth
def blacklist_add():
    """Numara ekler; Türk (05XX, 11 hane) veya uluslararası (7-15 hane) formatını kabul eder."""
    body = request.get_json(silent=True) or {}
    num = "".join(c for c in str(body.get("number", "")) if c.isdigit())
    if len(num) == 10:
        num = "0" + num
    if len(num) < 7 or len(num) > 15:
        return jsonify({"error": "Geçersiz numara (7-15 hane olmalı)"}), 400
    items = _load_blacklist()
    if num in items:
        return jsonify({"error": "Zaten listede"}), 409
    items.append(num)
    _atomic_write(BLACKLIST_PATH, json.dumps(items, ensure_ascii=False, indent=2))
    logger.info(f"Kara liste: {num} eklendi")
    return jsonify({"ok": True, "count": len(items)})


@app.route("/api/blacklist", methods=["DELETE"])
@require_auth
def blacklist_remove():
    """Numarayı kara listeden çıkarır."""
    body = request.get_json(silent=True) or {}
    num = str(body.get("number", "")).strip()
    items = _load_blacklist()
    if num not in items:
        return jsonify({"error": "Listede yok"}), 404
    items.remove(num)
    _atomic_write(BLACKLIST_PATH, json.dumps(items, ensure_ascii=False, indent=2))
    logger.info(f"Kara liste: {num} silindi")
    return jsonify({"ok": True, "count": len(items)})


# ---------------- API: Ayarlar ----------------

@app.route("/api/settings", methods=["GET"])
@require_auth
def settings_get():
    """Düzenlenebilir .env anahtarlarının güncel değerlerini döner."""
    values = {}
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    if k.strip() in EDITABLE_ENV_KEYS:
                        values[k.strip()] = v.strip()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    return jsonify({"settings": values, "editable": EDITABLE_ENV_KEYS})


@app.route("/api/settings", methods=["POST"])
@require_auth
def settings_save():
    """Gönderilen anahtarları .env'de günceller (sadece izinli anahtarlar)."""
    body = request.get_json(silent=True) or {}
    updates = {k: str(v).strip() for k, v in (body.get("settings") or {}).items() if k in EDITABLE_ENV_KEYS}
    if not updates:
        return jsonify({"error": "Güncellenecek ayar yok"}), 400
    try:
        with open(ENV_PATH, "r", encoding="utf-8") as f:
            lines = f.readlines()
        seen = set()
        out = []
        for line in lines:
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                k = stripped.split("=", 1)[0].strip()
                if k in updates:
                    out.append(f"{k}={updates[k]}\n")
                    seen.add(k)
                    continue
            out.append(line)
        for k, v in updates.items():
            if k not in seen:
                out.append(f"{k}={v}\n")
        _atomic_write(ENV_PATH, "".join(out))
        logger.info(f"Ayar güncellendi: {list(updates.keys())}")
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    restarted = False
    if body.get("restart"):
        ok, _ = _pm2(["restart", SERVICE_NAME])
        restarted = ok
    return jsonify({"ok": True, "restarted": restarted})


# ---------------- Arayüz (tek sayfa, mobil öncelikli) ----------------

INDEX_HTML = """<!DOCTYPE html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<title>Mavi Lojistik Panel</title>
<style>
:root{--bg:#f7f7f8;--card:#ffffff;--acc:#f39c12;--acc-dark:#d9840a;--acc-soft:#fff2e0;--ok:#16a34a;--warn:#f39c12;--err:#dc2626;--tx:#1f2937;--mut:#6b7280;--border:#e5e7eb}
*{box-sizing:border-box;margin:0;padding:0}
body{background:var(--bg);color:var(--tx);font-family:-apple-system,'Segoe UI',Roboto,sans-serif}
.hide{display:none!important}
#app{display:flex;min-height:100vh}
.sidebar{width:210px;flex-shrink:0;background:var(--card);border-right:1px solid var(--border);display:flex;flex-direction:column;overflow:hidden;transition:width .2s ease}
.sidebar.collapsed{width:64px}
.sidebar .brand{display:flex;align-items:center;gap:10px;padding:18px 16px;font-weight:700;font-size:15px;white-space:nowrap}
.sidebar .brand .logo{font-size:20px}
.sidebar.collapsed .brand .label{display:none}
.collapse-btn{border:0;background:none;color:var(--mut);width:auto;padding:0 16px 14px;text-align:left;cursor:pointer;font-size:16px}
.sidebar nav{display:flex;flex-direction:column;gap:2px;padding:8px;flex:1}
.sidebar nav button{display:flex;align-items:center;gap:12px;justify-content:flex-start;background:none;color:var(--mut);font-weight:600;font-size:14px;padding:11px 12px;border-radius:10px;width:100%;white-space:nowrap;cursor:pointer}
.sidebar nav button:hover{background:#f3f4f6}
.sidebar nav button.act{background:var(--acc-soft);color:var(--acc-dark)}
.sidebar.collapsed nav button{justify-content:center}
.sidebar.collapsed nav button .label{display:none}
main{flex:1;min-width:0;padding-bottom:24px}
header{padding:12px 16px;background:var(--card);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:8px}
#mob-menu-btn{display:none}
header h1{font-size:16px;font-weight:700}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:16px;margin:16px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.stat{text-align:center;padding:14px 8px;background:#fafafa;border:1px solid var(--border);border-radius:10px}
.stat b{font-size:20px;display:block}
.stat span{color:var(--mut);font-size:12px}
button{border:0;border-radius:10px;padding:13px;font-size:15px;font-weight:600;color:#fff;cursor:pointer}
.btn-full{width:100%}
.b-ok{background:var(--ok)}.b-err{background:var(--err)}.b-warn{background:var(--warn)}.b-acc{background:var(--acc)}
.row{display:flex;gap:8px;margin-top:10px}
input,select{width:100%;padding:12px;border-radius:10px;border:1px solid var(--border);background:#fff;color:var(--tx);font-size:15px}
select{width:auto}
.split{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:16px}
.split .card{margin:0}
.msg-layout{display:flex;gap:16px;margin:16px;align-items:flex-start}
.msg-ships{flex:1;min-width:0}
.msg-orig{flex-shrink:0;flex-basis:35%;min-width:260px}
.ship-card{border:1px solid var(--border);border-left:3px solid var(--acc);border-radius:8px;padding:12px 14px;margin-bottom:8px}
.ship-route{font-weight:700;font-size:14px;color:var(--tx);margin-bottom:4px}
.ship-tags{display:flex;flex-wrap:wrap;gap:6px;margin:6px 0}
.ship-tag{background:var(--acc-soft);color:var(--acc-dark);border-radius:12px;padding:2px 10px;font-size:11px}
.tag-toggle{background:var(--bg);color:var(--mut);border:1px solid var(--border);border-radius:12px;padding:4px 12px;font-size:12px;font-weight:600;cursor:pointer}
.tag-toggle.tag-on{background:var(--acc);color:#fff;border-color:var(--acc)}
@keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(1.4)}}
.dot-pulse{animation:pulse 1s ease-in-out infinite}
.ship-actions{display:flex;gap:8px;margin-top:8px}
.ship-actions button{width:auto!important;padding:6px 16px!important;font-size:12px!important;font-weight:600!important}
pre{background:#0f172a;color:#d1d5db;padding:10px;border-radius:10px;font-size:11px;overflow:auto;max-height:60vh;white-space:pre-wrap;word-break:break-all}
.bl-item{display:flex;justify-content:space-between;align-items:center;padding:9px 4px;border-bottom:1px solid var(--border);font-size:14px}
.bl-item button{width:auto;padding:6px 12px;font-size:12px}
label{color:var(--mut);font-size:12px;display:block;margin:10px 0 4px}
#toast{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:var(--acc);color:#fff;padding:10px 18px;border-radius:10px;font-size:14px;z-index:20;transition:.3s;opacity:0}
.login-wrap{max-width:340px;margin:25vh auto;padding:0 16px;text-align:center}
.login-wrap h2{margin-bottom:18px}
@media (max-width:768px){
  .wrap{position:relative}
  .sidebar{position:fixed;left:-210px;top:0;bottom:0;z-index:20;transition:left .2s ease,width .2s ease;width:210px;box-shadow:2px 0 12px rgba(0,0,0,.15)}
  .sidebar.open{left:0}
  .sidebar.collapsed{left:0;width:64px;box-shadow:none}
  #mob-overlay{display:none;position:fixed;inset:0;z-index:19;background:rgba(0,0,0,.35)}
  #mob-overlay.show{display:block}
  main{margin-left:0!important}
  .split{grid-template-columns:1fr}
  .msg-layout{flex-direction:column}
  .msg-orig{width:100%}
  .grid{grid-template-columns:repeat(2,1fr)}
  .collapse-btn{display:block}
  #mob-menu-btn{display:flex}
}
</style>
</head>
<body>

<div id="login" class="login-wrap">
  <h2>🚛 Mavi Lojistik</h2>
  <input id="pwd" type="password" placeholder="Panel şifresi" autocomplete="current-password">
  <div style="height:10px"></div>
  <button class="b-acc btn-full" onclick="doLogin()">Giriş</button>
</div>

<div id="app" class="hide">
<aside class="sidebar" id="sidebar">
  <div class="brand"><span class="logo">🚛</span><span class="label">Mavi Lojistik</span></div>
  <button class="collapse-btn" onclick="toggleSidebar()" title="Daralt/Genişlet">☰</button>
  <nav>
    <button class="act" onclick="tab('status',this)"><span class="ic">📊</span><span class="label">Durum</span></button>
    <button onclick="tab('msg',this);loadMessages()"><span class="ic">💬</span><span class="label">Mesajlar</span></button>
    <button onclick="tab('grp',this);loadGrpTab()"><span class="ic">👥</span><span class="label">Gruplar</span></button>
    <button onclick="tab('logs',this);loadLogs();_startLogTimer()"><span class="ic">📜</span><span class="label">Loglar</span></button>
    <button onclick="tab('sent',this);loadSent()"><span class="ic">📤</span><span class="label">Gönderilenler</span></button>
    <button onclick="tab('billing',this)"><span class="ic">💳</span><span class="label">Billing</span></button>
    <button onclick="tab('bl',this);loadBl()"><span class="ic">🚫</span><span class="label">Kara Liste</span></button>
    <button onclick="tab('set',this);loadSet()"><span class="ic">⚙️</span><span class="label">Ayarlar</span></button>
  </nav>
</aside>
<div id="mob-overlay" onclick="closeMobSidebar()"></div>
<main>
<header>
  <button id="mob-menu-btn" onclick="toggleMobSidebar()" style="display:none;width:auto;padding:6px 10px;background:none;color:var(--tx);font-size:20px;margin-right:8px">☰</button>
  <h1 style="flex:1">Mavi Lojistik Panel</h1>
  <span id="svcdot"><span class="dot" style="background:var(--mut)"></span><span id="svctxt">...</span></span>
</header>

<div id="tab-status">
  <div class="card">
    <div class="grid">
      <div class="stat"><b id="s-cpu">–</b><span>CPU %</span></div>
      <div class="stat"><b id="s-mem">–</b><span>Servis RAM (MB)</span></div>
      <div class="stat"><b id="s-ram">–</b><span>Sunucu RAM %</span></div>
      <div class="stat"><b id="s-disk">–</b><span>Disk %</span></div>
    </div>
    <div class="row">
      <button class="b-ok btn-full" onclick="svc('start')">▶ Başlat</button>
      <button class="b-warn btn-full" onclick="svc('restart')">⟳ Restart</button>
      <button class="b-err btn-full" onclick="if(confirm('Servis durdurulsun mu?'))svc('stop')">■ Durdur</button>
    </div>
    <p id="s-extra" style="color:var(--mut);font-size:12px;margin-top:10px"></p>
  </div>
</div>

<div id="tab-msg" class="hide">
  <div class="card" style="margin:16px 16px 8px;padding:10px 14px">
    <div style="display:flex;align-items:center;gap:8px;flex-wrap:nowrap;overflow-x:auto">
      <button class="b-acc" onclick="msgNav(-1)" style="width:auto;font-size:16px;padding:4px 12px;flex-shrink:0">‹</button>
      <span id="msg-nav-txt" style="font-size:13px;color:var(--mut);min-width:40px;text-align:center;flex-shrink:0">0/0</span>
      <button class="b-acc" onclick="msgNav(1)" style="width:auto;font-size:16px;padding:4px 12px;flex-shrink:0">›</button>
      <select id="msg-filter" onchange="loadMessages()" style="width:auto;font-size:12px;padding:5px 8px;flex-shrink:0">
        <option value="10">Son 10 Dk</option>
        <option value="60" selected>Son 1 Saat</option>
        <option value="1440">Bugün</option>
        <option value="all">Tümü</option>
      </select>
      <button class="b-acc" onclick="loadMessages()" style="width:auto;padding:5px 10px;font-size:12px;flex-shrink:0">⟳</button>
      <span id="ship-count" style="font-size:12px;color:var(--mut);flex-shrink:0"></span>
      <button id="auto-btn" onclick="toggleAutoApprove()" style="margin-left:auto;width:auto;padding:5px 12px;font-size:12px;font-weight:700;border-radius:20px;background:#374151;color:#fff;flex-shrink:0;display:flex;align-items:center;gap:6px;transition:background .3s">
        <span id="auto-dot" style="width:8px;height:8px;border-radius:50%;background:#6b7280;display:inline-block;transition:background .3s"></span>
        <span id="auto-txt">Oto Onay</span>
      </button>
    </div>
  </div>
  <div class="msg-layout">
    <div class="card msg-ships" style="margin:0">
      <b style="font-size:13px;color:var(--tx)">🚛 Sevkiyatlar</b>
      <div id="ship-list" style="margin-top:10px"><p style="color:var(--mut);font-size:13px">Yükleniyor...</p></div>
    </div>
    <div class="card msg-orig" style="margin:0">
      <b style="color:var(--mut);font-size:11px;text-transform:uppercase;letter-spacing:.5px">Orijinal Mesaj</b>
      <div id="msg-meta" style="margin-top:6px;font-size:11px;color:var(--mut)"></div>
      <div id="msg-original" style="margin-top:8px;font-size:13px;white-space:pre-wrap;color:var(--tx);max-height:60vh;overflow-y:auto">
        <span style="color:var(--mut)">Yükleniyor...</span>
      </div>
    </div>
  </div>
</div>

<div id="tab-billing" class="hide">
  <div class="card" style="margin:16px;max-width:420px">
    <b style="font-size:15px">💳 Billing</b>
    <div style="display:flex;flex-direction:column;gap:12px;margin-top:16px">
      <a href="https://whapi.cloud/" target="_blank" style="display:flex;align-items:center;gap:14px;padding:16px;background:var(--bg);border-radius:12px;border:1px solid var(--border);text-decoration:none;color:var(--tx)">
        <span style="font-size:28px">📱</span>
        <div>
          <div style="font-weight:700;font-size:14px">Whapi</div>
          <div style="font-size:12px;color:var(--mut)">WhatsApp API ödeme ve kullanım</div>
        </div>
        <span style="margin-left:auto;color:var(--mut)">→</span>
      </a>
      <a href="https://platform.deepseek.com/usage" target="_blank" style="display:flex;align-items:center;gap:14px;padding:16px;background:var(--bg);border-radius:12px;border:1px solid var(--border);text-decoration:none;color:var(--tx)">
        <span style="font-size:28px">🤖</span>
        <div>
          <div style="font-weight:700;font-size:14px">DeepSeek</div>
          <div style="font-size:12px;color:var(--mut)">AI kullanim ve kredi</div>
        </div>
        <span style="margin-left:auto;color:var(--mut)">→</span>
      </a>
    </div>
  </div>
</div>

<div id="tab-sent" class="hide">
  <div class="card" style="margin:16px 16px 8px;padding:10px 14px">
    <div style="display:flex;align-items:center;gap:8px">
      <b style="font-size:14px">📤 Gönderilenler</b>
      <button class="b-acc" onclick="loadSent()" style="width:auto;padding:5px 10px;font-size:12px;margin-left:auto">⟳ Yenile</button>
      <span id="sent-count" style="font-size:12px;color:var(--mut)"></span>
    </div>
  </div>
  <div class="card" style="margin:0 16px">
    <div id="sent-list"><p style="color:var(--mut);font-size:13px">Yükleniyor...</p></div>
  </div>
</div>

<div id="tab-grp" class="hide">
  <div style="margin:12px 16px 0;display:flex;align-items:center;gap:10px;flex-wrap:wrap">
    <div id="wa-health-badge" style="display:flex;align-items:center;gap:6px;padding:6px 14px;border-radius:20px;background:#f3f4f6;font-size:12px;font-weight:700;cursor:pointer" onclick="checkWaHealth()">
      <span id="wa-health-dot" style="width:8px;height:8px;border-radius:50%;background:#6b7280;display:inline-block"></span>
      <span id="wa-health-txt">WhatsApp kontrol ediliyor...</span>
    </div>
    <a id="wa-health-link" href="https://app.whapi.cloud/" target="_blank" style="display:none;font-size:12px;color:var(--err);font-weight:700;text-decoration:underline">→ Whapi Paneli</a>
  </div>
  <div class="split">
    <div class="card">
      <div class="row" style="margin:0 0 10px">
        <button class="b-acc btn-full" onclick="loadGroups()">⟳ Kayıtlı Gruplar</button>
      </div>
      <p id="grp-count" style="color:var(--mut);font-size:12px;margin:0 0 4px"></p>
      <div id="grp-list"></div>
    </div>
    <div class="card">
      <div class="row" style="margin:0 0 6px">
        <button class="b-warn btn-full" onclick="loadAvailableGroups(true)">🔄 Whapi'dan Yeniden Çek</button>
      </div>
      <p id="grp-available-count" style="color:var(--mut);font-size:12px;margin:0 0 6px"></p>
      <label style="font-size:11px;color:var(--mut)">Kayıtsız gruplar önce listelenir</label>
      <div id="grp-available-list" style="margin-top:6px"><p style="color:var(--mut);font-size:13px">Yükleniyor...</p></div>
    </div>
  </div>
</div>

<div id="tab-logs" class="hide">
  <div class="card">
    <div style="display:flex;justify-content:space-between;align-items:center;margin:0 0 10px">
      <b style="font-size:13px;color:var(--tx)">📜 Loglar</b>
      <span id="log-timer" style="font-size:11px;color:var(--mut)">⟳ 5s</span>
    </div>
    <pre id="logbox">Yükleniyor...</pre>
  </div>
</div>

<div id="tab-bl" class="hide">
  <div class="card">
    <div class="row" style="margin:0">
      <input id="bl-new" placeholder="05XXXXXXXXX veya uluslararasi" inputmode="numeric">
      <button class="b-ok" style="width:90px" onclick="blAdd()">Ekle</button>
    </div>
    <div class="row" style="margin-top:8px">
      <input id="bl-q" placeholder="Ara..." oninput="loadBl()">
    </div>
    <p id="bl-count" style="color:var(--mut);font-size:12px;margin:10px 0 4px"></p>
    <div id="bl-list"></div>
  </div>
</div>

<div id="tab-set" class="hide">
  <div class="card">
    <div id="set-fields"></div>
    <div class="row">
      <button class="b-acc btn-full" onclick="saveSet(false)">Kaydet</button>
      <button class="b-warn btn-full" onclick="saveSet(true)">Kaydet + Restart</button>
    </div>
    <p style="color:var(--mut);font-size:11px;margin-top:8px">Ayarların etkili olması için servisin yeniden başlatılması gerekir.</p>
  </div>
</div>
</main>
</div>

<div id="toast"></div>

<script>
let TOK = localStorage.getItem('tok') || '';
const $ = id => document.getElementById(id);

function isMob(){ return window.innerWidth <= 768; }

function toggleSidebar(){
  if(isMob()){ toggleMobSidebar(); return; }
  const sb = $('sidebar');
  sb.classList.toggle('collapsed');
  localStorage.setItem('sbCollapsed', sb.classList.contains('collapsed') ? '1' : '0');
}

function toggleMobSidebar(){
  const sb = $('sidebar');
  const ov = $('mob-overlay');
  const open = sb.classList.toggle('open');
  ov.classList.toggle('show', open);
}

function closeMobSidebar(){
  $('sidebar').classList.remove('open');
  $('mob-overlay').classList.remove('show');
}

(function initSidebar(){
  if(isMob()){
    $('mob-menu-btn').style.display='flex';
    // mobilde sidebar zaten gizli (left:-210px), collapsed ekleme
    return;
  }
  const stored = localStorage.getItem('sbCollapsed');
  const collapsed = stored !== null ? stored === '1' : false;
  if(collapsed) $('sidebar').classList.add('collapsed');
})();

function toast(m, err){const t=$('toast');t.textContent=m;t.style.background=err?'var(--err)':'var(--acc)';t.style.opacity=1;setTimeout(()=>t.style.opacity=0,2500);}

async function api(path, opt={}){
  opt.headers = Object.assign({'Content-Type':'application/json','Authorization':'Bearer '+TOK}, opt.headers||{});
  const r = await fetch(path, opt);
  if(r.status===401 && path!=='/api/login'){localStorage.removeItem('tok');location.reload();return null;}
  return r.json();
}

async function doLogin(){
  const r = await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({password:$('pwd').value})});
  const d = await r.json();
  if(d.token){TOK=d.token;localStorage.setItem('tok',TOK);start();}
  else toast(d.error||'Hata', true);
}

function tab(name, btn){
  ['status','msg','sent','billing','grp','logs','bl','set'].forEach(t=>$('tab-'+t).classList.add('hide'));
  $('tab-'+name).classList.remove('hide');
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('act'));
  if(btn)btn.classList.add('act');
  if(name !== 'logs') _stopLogTimer();
  if(isMob()) closeMobSidebar();
}

async function refresh(){
  const d = await api('/api/status'); if(!d) return;
  const s = d.service, on = s.status==='online';
  $('svctxt').textContent = s.status;
  document.querySelector('#svcdot .dot').style.background = on?'var(--ok)':'var(--err)';
  $('s-cpu').textContent = s.cpu; $('s-mem').textContent = s.memory;
  if(d.system){$('s-ram').textContent=d.system.ram_pct; $('s-disk').textContent=d.system.disk_pct;
    $('s-extra').textContent = `Restart sayısı: ${s.restarts} • Load: ${d.system.load} • RAM: ${d.system.ram_used_mb}/${d.system.ram_total_mb} MB`;}
}

async function svc(a){
  toast('İşlem gönderildi...');
  const d = await api('/api/service/'+a,{method:'POST'});
  if(d) toast(d.ok?'Tamamlandı ✓':('Hata: '+d.output), !d.ok);
  setTimeout(refresh, 2500);
}

function escapeHtml(s){
  return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}

let _unprocessedMsgs = [];
let _msgIdx = 0;

function _currentMsg(){ return _unprocessedMsgs[_msgIdx] || null; }

async function loadMessages(){
  const minutes = $('msg-filter').value;
  const d = await api('/api/unprocessed?minutes='+minutes); if(!d) return;
  const prevId = _currentMsg()?.message_id;
  _unprocessedMsgs = d.messages || [];
  // Önceki mesaj hala varsa o indekste kal, yoksa 0
  if(prevId){
    const idx = _unprocessedMsgs.findIndex(m=>m.message_id===prevId);
    _msgIdx = idx >= 0 ? idx : 0;
  } else {
    _msgIdx = 0;
  }
  _renderCurrentMsg();
}

function msgNav(dir){
  if(!_unprocessedMsgs.length) return;
  _msgIdx = (_msgIdx + dir + _unprocessedMsgs.length) % _unprocessedMsgs.length;
  _renderCurrentMsg();
}

function _renderCurrentMsg(){
  const total = _unprocessedMsgs.length;
  $('msg-nav-txt').textContent = total ? (_msgIdx+1)+'/'+total : '0/0';
  const msg = _currentMsg();
  if(!msg){
    $('msg-original').innerHTML='<span style="color:var(--mut)">Bekleyen mesaj yok.</span>';
    $('msg-meta').textContent='';
    $('ship-count').textContent='';
    $('ship-list').innerHTML='<p style="color:var(--mut);font-size:13px">Bekleyen mesaj yok.</p>';
    return;
  }
  // Sağ: orijinal mesaj
  const info = msg.message_info||{};
  $('msg-original').textContent = info.body||'İçerik yok';
  const parts=[];
  if(info.chat_name) parts.push('📱 '+info.chat_name);
  if(info.sender) parts.push('👤 '+info.sender);
  if(info.timestamp){const dt=new Date(info.timestamp*1000);parts.push('🕐 '+dt.toLocaleString('tr-TR'));}
  $('msg-meta').textContent = parts.join('  |  ');
  // Sol: sevkiyatlar
  const ships = msg.shipments||[];
  $('ship-count').textContent = ships.length+' sevkiyat';
  if(!ships.length){
    $('ship-list').innerHTML='<p style="color:var(--mut);font-size:13px">Bu mesajda sevkiyat yok.</p>';
    return;
  }
  const arr=v=>Array.isArray(v)?v:(v?[v]:[]);
  const mid = msg.message_id;
  // Toplu işlem butonları
  const bulkHtml = `<div style="display:flex;gap:8px;margin-bottom:10px">
    <button class="b-ok" style="flex:1;padding:8px;font-size:13px;font-weight:700" onclick="approveAll('${mid}')">✓ Tümünü Onayla (${ships.length})</button>
    <button class="b-err" style="flex:1;padding:8px;font-size:13px;font-weight:700" onclick="deleteMsg('${mid}')">✕ Tümünü Sil</button>
  </div>`;
  $('ship-list').innerHTML = bulkHtml + ships.map((s,i)=>{
    const from=(s.nereden_il||s.nerden_il||'?')+(s.nereden_ilce||s.nerden_ilce?'/'+(s.nereden_ilce||s.nerden_ilce):'');
    const to=(s.nereye_il||'?')+(s.nereye_ilce?'/'+s.nereye_ilce:'');
    const tags=[];
    arr(s.arac_tipi).forEach(v=>v&&tags.push('🚛 '+v));
    arr(s.kasa_tipi).forEach(v=>v&&tags.push('📦 '+v));
    arr(s.yuk_tipi).forEach(v=>v&&tags.push('⚡ '+v));
    if(s.fiyat&&s.fiyat!=='SORUNUZ') tags.push('💰 '+s.fiyat);
    const phone = arr(s.telefon).filter(Boolean);
    const midE = encodeURIComponent(mid);
    return `<div class="ship-card">
      <div style="display:flex;align-items:flex-start;gap:6px">
        <div style="flex:1">
          <div class="ship-route">${escapeHtml(from)} → ${escapeHtml(to)}</div>
          ${s.isim&&s.isim!=='SORUNUZ'?`<div style="font-size:12px;color:var(--mut)">${escapeHtml(s.isim)}</div>`:''}
          <div class="ship-tags">${tags.map(t=>`<span class="ship-tag">${escapeHtml(t)}</span>`).join('')}</div>
          ${phone.length?`<div style="font-size:12px;color:var(--mut)">📞 ${escapeHtml(phone.join(', '))}</div>`:''}
        </div>
        <button onclick="openEditModal('${midE}',${i})" style="width:auto;padding:4px 10px;font-size:12px;background:var(--acc);color:#fff;border-radius:8px;flex-shrink:0">✏️</button>
      </div>
    </div>`;
  }).join('');
}

// ======= OTO ONAY (sunucu tarafli) =======
function _renderAutoBtn(enabled){
  const btn = $('auto-btn');
  const dot = $('auto-dot');
  const txt = $('auto-txt');
  if(!btn) return;
  if(enabled){
    btn.style.background = '#16a34a';
    dot.style.background = '#86efac';
    dot.classList.add('dot-pulse');
    txt.textContent = 'Oto Onay ACIK';
  } else {
    btn.style.background = '#374151';
    dot.style.background = '#6b7280';
    dot.classList.remove('dot-pulse');
    txt.textContent = 'Oto Onay';
  }
}

let _autoEnabled = false;
async function syncAutoApprove(){
  const d = await api('/api/auto-approve');
  if(d && typeof d.enabled === 'boolean'){
    _autoEnabled = d.enabled;
    _renderAutoBtn(_autoEnabled);
  }
}

async function toggleAutoApprove(){
  const d = await api('/api/auto-approve',{method:'POST',body:JSON.stringify({enabled:!_autoEnabled})});
  if(d && d.ok){
    _autoEnabled = d.enabled;
    _renderAutoBtn(_autoEnabled);
    toast(_autoEnabled ? 'Oto onay ACILDI (sunucuda calisiyor)' : 'Oto onay kapatildi');
  } else if(d) toast(d.error||'Hata', true);
}
// ======= OTO ONAY SONU =======

async function approveAll(msgId){
  if(!confirm('Tum sevkiyatlar onaylansin ve YukBurada gonderilsin mi?')) return;
  const d = await api('/api/unprocessed/'+encodeURIComponent(msgId)+'/approve_all',{method:'POST'});
  if(d&&d.ok){
    toast('✓ '+d.count+' sevkiyat onaylandı');
    _unprocessedMsgs = _unprocessedMsgs.filter(m=>m.message_id!==msgId);
    if(_msgIdx >= _unprocessedMsgs.length) _msgIdx = Math.max(0, _unprocessedMsgs.length-1);
    _renderCurrentMsg();
    $('msg-nav-txt').textContent = _unprocessedMsgs.length ? (_msgIdx+1)+'/'+_unprocessedMsgs.length : '0/0';
  } else if(d) toast(d.error||'Hata',true);
}

async function deleteMsg(msgId){
  if(!confirm('Bu mesaj ve tüm sevkiyatları silinsin mi?')) return;
  const d = await api('/api/unprocessed/'+encodeURIComponent(msgId),{method:'DELETE'});
  if(d&&d.ok){
    toast('Silindi');
    _unprocessedMsgs = _unprocessedMsgs.filter(m=>m.message_id!==msgId);
    if(_msgIdx >= _unprocessedMsgs.length) _msgIdx = Math.max(0, _unprocessedMsgs.length-1);
    _renderCurrentMsg();
    $('msg-nav-txt').textContent = _unprocessedMsgs.length ? (_msgIdx+1)+'/'+_unprocessedMsgs.length : '0/0';
  } else if(d) toast(d.error||'Hata',true);
}

async function checkWaHealth(){
  $('wa-health-txt').textContent = 'Kontrol ediliyor...';
  $('wa-health-dot').style.background = '#6b7280';
  $('wa-health-link').style.display = 'none';
  const d = await api('/api/whatsapp-health');
  if(!d) return;
  const ok = d.status === 'ok';
  const dot = $('wa-health-dot');
  const txt = $('wa-health-txt');
  const badge = $('wa-health-badge');
  const link = $('wa-health-link');
  dot.style.background = ok ? '#16a34a' : '#dc2626';
  txt.textContent = ok ? 'WhatsApp Bagli (' + (d.detail||'ok') + ')' : 'WhatsApp Baglanti Sorunu: ' + (d.detail||'hata');
  badge.style.background = ok ? '#dcfce7' : '#fee2e2';
  link.style.display = ok ? 'none' : 'inline';
}

async function loadGrpTab(){
  loadGroups();
  loadAvailableGroups();
  checkWaHealth();
}

async function loadGroups(){
  const d = await api('/api/groups'); if(!d) return;
  $('grp-count').textContent = `Kayıtlı ${d.groups.length} grup`;
  $('grp-list').innerHTML = d.groups.map(g =>
    `<div class="bl-item"><span>${escapeHtml(g.name)}</span><button class="b-err" onclick="grpDel('${g.id}')">Sil</button></div>`).join('');
}

async function loadAvailableGroups(force=false){
  $('grp-available-list').innerHTML = '<p style="color:var(--mut);font-size:13px">Sunucudan cekiliyor...</p>';
  const d = await api('/api/groups/available'+(force?'?force=1':'')); if(!d) return;
  if(d.error){$('grp-available-list').innerHTML = `<p style="color:var(--err);font-size:13px">${escapeHtml(d.error)}</p>`; return;}
  const unsaved = d.groups.filter(g=>!g.saved).length;
  const saved   = d.groups.filter(g=>g.saved).length;
  const cacheNote = d.cached ? ' <span style="color:var(--mut);font-weight:400">(önbellek)</span>' : '';
  $('grp-available-count').innerHTML = `${d.groups.length} grup — <span style="color:var(--err)">${unsaved} kayıtsız</span> / <span style="color:var(--ok)">${saved} kayıtlı</span>${cacheNote}`;
  $('grp-available-list').innerHTML = d.groups.map(g => `
    <div class="bl-item">
      <span>${escapeHtml(g.name)}${g.saved ? ' <span style="color:var(--ok);font-size:11px">(kayıtlı)</span>' : ''}</span>
      ${g.saved ? '' : `<button class="b-ok" onclick="grpAdd('${g.id}','${escapeHtml(g.name).replace(/'/g,"\\'")}')">Ekle</button>`}
    </div>`).join('');
}

async function grpAdd(id, name){
  const d = await api('/api/groups',{method:'POST',body:JSON.stringify({id,name})});
  if(d&&d.ok){
    const ts = new Date().toLocaleTimeString('tr-TR');
    toast(`Eklendi ✓ — ${name} (${ts})`);
    await Promise.all([loadGroups(), loadAvailableGroups()]);
    _grpFlash('grp-count');
  } else if(d) toast(d.error,true);
}

async function grpDel(id){
  const card = event.target.closest('.bl-item');
  const name = card ? card.querySelector('span').textContent.trim() : id;
  if(!confirm(`"${name}" silinsin mi?`))return;
  const d = await api('/api/groups/'+encodeURIComponent(id),{method:'DELETE'});
  if(d&&d.ok){
    const ts = new Date().toLocaleTimeString('tr-TR');
    toast(`Silindi ✓ — ${name} (${ts})`);
    await Promise.all([loadGroups(), loadAvailableGroups()]);
    _grpFlash('grp-count');
  } else if(d) toast(d.error,true);
}

function _grpFlash(elId){
  const el = $(elId); if(!el) return;
  el.style.transition='none';
  el.style.color='#16a34a';
  el.style.fontWeight='700';
  setTimeout(()=>{ el.style.transition='color 1s'; el.style.color=''; el.style.fontWeight=''; }, 1500);
}

let _logInterval = null;
let _logCountdown = 5;

async function loadLogs(){
  const d = await api('/api/logs?lines=150'); if(!d) return;
  const box = $('logbox');
  const atBottom = box.scrollHeight - box.scrollTop - box.clientHeight < 40;
  box.textContent = d.logs;
  if(atBottom) box.scrollTop = box.scrollHeight;
}

function _startLogTimer(){
  if(_logInterval) return;
  _logCountdown = 5;
  _logInterval = setInterval(async ()=>{
    _logCountdown--;
    const t = $('log-timer');
    if(t) t.textContent = `⟳ ${_logCountdown}s`;
    if(_logCountdown <= 0){
      _logCountdown = 5;
      await loadLogs();
    }
  }, 1000);
}

function _stopLogTimer(){
  if(_logInterval){ clearInterval(_logInterval); _logInterval=null; }
}

async function loadSent(){
  $('sent-list').innerHTML='<p style="color:var(--mut);font-size:13px">YukBurada cekiliyor...</p>';
  const d = await api('/api/sent'); if(!d) return;
  if(d.error){$('sent-list').innerHTML=`<p style="color:var(--err)">${d.error}</p>`;return;}
  const loads = d.loads||[];
  $('sent-count').textContent = loads.length+' ilan';
  if(!loads.length){$('sent-list').innerHTML='<p style="color:var(--mut);font-size:13px">YukBurada ilan bulunamadi.</p>';return;}
  $('sent-list').innerHTML = loads.map(l=>{
    const from = l.pickupCity||l.pickupDistrict||'?';
    const to = l.deliveryCity||l.deliveryDistrict||'?';
    const owner = l.ownerPhone||l.phone||l.ownerUserId||'-';
    const date = l.createdAt ? new Date(l.createdAt).toLocaleString('tr-TR') : (l.updatedAt ? new Date(l.updatedAt).toLocaleString('tr-TR') : '-');
    const weight = l.weight ? l.weight+'t' : '';
    const status = l.status===0?'<span style="color:var(--ok);font-weight:700">Aktif</span>':'<span style="color:var(--mut)">Pasif</span>';
    return `<div style="display:flex;align-items:center;gap:10px;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">
      <span style="font-weight:700;min-width:130px">${from} → ${to}</span>
      <span style="color:var(--mut);flex:1">${owner}</span>
      <span style="color:var(--mut);min-width:90px">${weight}</span>
      <span style="min-width:120px;text-align:right;color:var(--mut)">${date}</span>
      <span style="min-width:50px;text-align:right">${status}</span>
    </div>`;
  }).join('');
}

async function loadBl(){
  const q = encodeURIComponent($('bl-q').value.trim());
  const d = await api('/api/blacklist?q='+q); if(!d) return;
  $('bl-count').textContent = `Toplam ${d.count} numara` + (q?` (filtre: ${d.items.length})`:'');
  $('bl-list').innerHTML = d.items.map(n=>`<div class="bl-item"><span>${n}</span><button class="b-err" onclick="blDel('${n}')">Sil</button></div>`).join('');
}

async function blAdd(){
  const d = await api('/api/blacklist',{method:'POST',body:JSON.stringify({number:$('bl-new').value})});
  if(d&&d.ok){toast('Eklendi ✓');$('bl-new').value='';loadBl();} else if(d) toast(d.error,true);
}

async function blDel(n){
  if(!confirm(n+' silinsin mi?'))return;
  const d = await api('/api/blacklist',{method:'DELETE',body:JSON.stringify({number:n})});
  if(d&&d.ok){toast('Silindi ✓');loadBl();} else if(d) toast(d.error,true);
}

async function loadSet(){
  const d = await api('/api/settings'); if(!d) return;
  $('set-fields').innerHTML = d.editable.map(k=>
    `<label>${k}</label><input data-k="${k}" value="${d.settings[k]??''}">`).join('');
}

async function saveSet(restart){
  const settings = {};
  document.querySelectorAll('#set-fields input').forEach(i=>settings[i.dataset.k]=i.value);
  const d = await api('/api/settings',{method:'POST',body:JSON.stringify({settings,restart})});
  if(d&&d.ok) toast(restart?(d.restarted?'Kaydedildi + Restart ✓':'Kaydedildi, restart HATA'):'Kaydedildi ✓', restart&&!d.restarted);
  else if(d) toast(d.error,true);
}

function start(){
  $('login').classList.add('hide');$('app').classList.remove('hide');
  refresh(); setInterval(refresh, 10000);
  syncAutoApprove(); // sunucudaki oto onay durumunu goster
  setInterval(syncAutoApprove, 15000);
}
if(TOK){ api('/api/status').then(d=>{ if(d) start(); }); }
$('pwd').addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();});

// ===================== DÜZENLE MODAL =====================
let _formData = null; // {il_ilce, types}
let _editMsgId = null;
let _editShipIdx = null;
let _editShip = null;

async function _ensureFormData(){
  if(_formData) return _formData;
  const d = await api('/api/form-data');
  if(d) _formData = d;
  return _formData;
}

async function openEditModal(msgId, shipIdx){
  const fd = await _ensureFormData();
  if(!fd){ toast('Form verisi yuklenemedi', true); return; }
  const msg = _unprocessedMsgs.find(m=>m.message_id===decodeURIComponent(msgId));
  if(!msg){ toast('Mesaj bulunamadi', true); return; }
  const ship = (msg.shipments||[])[shipIdx];
  if(!ship){ toast('Sevkiyat bulunamadi', true); return; }
  _editMsgId = msg.message_id;
  _editShipIdx = shipIdx;
  _editShip = JSON.parse(JSON.stringify(ship)); // deep copy for editing

  const ilList = fd.il_ilce.map(x=>x.il);
  const ilceMap = {};
  fd.il_ilce.forEach(x=>{ ilceMap[x.il] = x.ilceler; });
  const arac = fd.types.arac_tipleri||[];
  const kasa = fd.types.kasa_tipleri||[];
  const yuk  = fd.types.yuk_tipleri||[];

  const arr = v=>Array.isArray(v)?v:(v?[v]:[]);
  const selArac = arr(ship.arac_tipi).filter(Boolean);
  const selKasa = arr(ship.kasa_tipi).filter(Boolean);
  const selYuk  = arr(ship.yuk_tipi).filter(Boolean);
  const tel = arr(ship.telefon).filter(Boolean).join(', ');

  const nIl = (ship.nereden_il||'').toUpperCase();
  const nIlce = ship.nereden_ilce||'';
  const yIl = (ship.nereye_il||'').toUpperCase();
  const yIlce = ship.nereye_ilce||'';

  function ilOpts(sel){ return ilList.map(il=>`<option value="${il}"${il===sel?' selected':''}>${il}</option>`).join(''); }
  function ilceOpts(il, sel){
    const list = ilceMap[il]||[];
    return list.map(ilce=>`<option value="${ilce}"${ilce===sel?' selected':''}>${ilce}</option>`).join('');
  }
  function tagBtns(list, sel, field){
    return list.map(v=>{
      const on = sel.includes(v);
      return `<button type="button" class="tag-toggle${on?' tag-on':''}" data-field="${field}" data-val="${v}" onclick="_toggleTag(this)">${v}</button>`;
    }).join('');
  }

  const html = `<div id="edit-overlay" onclick="if(event.target===this)closeEdit()" style="position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:999;display:flex;align-items:flex-start;justify-content:center;padding:20px;overflow-y:auto">
  <div style="background:var(--card);border-radius:16px;padding:20px;width:100%;max-width:520px;position:relative" onclick="event.stopPropagation()">
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:16px">
      <b style="font-size:15px">Sevkiyat Duzenle</b>
      <button onclick="closeEdit()" style="width:auto;padding:4px 12px;background:var(--mut);color:#fff;border-radius:8px">✕</button>
    </div>
    <div style="display:flex;flex-direction:column;gap:12px">
      <div>
        <label style="font-size:12px;font-weight:700;color:var(--mut)">FIRMA ADI</label>
        <input id="ef-isim" value="${escapeHtml(ship.isim||'')}" style="width:100%;margin-top:4px;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg);color:var(--tx)">
      </div>
      <div style="display:flex;gap:8px;align-items:flex-end">
        <div style="flex:1">
          <label style="font-size:12px;font-weight:700;color:var(--mut)">NEREDEN IL</label>
          <select id="ef-n-il" onchange="_updateIlce('n')" style="width:100%;margin-top:4px;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg);color:var(--tx)">${ilOpts(nIl)}</select>
        </div>
        <div style="flex:1">
          <label style="font-size:12px;font-weight:700;color:var(--mut)">NEREDEN ILCE</label>
          <select id="ef-n-ilce" style="width:100%;margin-top:4px;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg);color:var(--tx)">${ilceOpts(nIl,nIlce)}</select>
        </div>
        <button type="button" onclick="_swapLoc()" style="width:auto;padding:8px 10px;background:var(--acc);color:#fff;border-radius:8px;flex-shrink:0" title="Yer Degistir">⇄</button>
      </div>
      <div style="display:flex;gap:8px">
        <div style="flex:1">
          <label style="font-size:12px;font-weight:700;color:var(--mut)">NEREYE IL</label>
          <select id="ef-y-il" onchange="_updateIlce('y')" style="width:100%;margin-top:4px;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg);color:var(--tx)">${ilOpts(yIl)}</select>
        </div>
        <div style="flex:1">
          <label style="font-size:12px;font-weight:700;color:var(--mut)">NEREYE ILCE</label>
          <select id="ef-y-ilce" style="width:100%;margin-top:4px;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg);color:var(--tx)">${ilceOpts(yIl,yIlce)}</select>
        </div>
      </div>
      <div>
        <label style="font-size:12px;font-weight:700;color:var(--mut)">ARAC TIPI</label>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">${tagBtns(arac,selArac,'arac')}</div>
      </div>
      <div>
        <label style="font-size:12px;font-weight:700;color:var(--mut)">KASA TIPI</label>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">${tagBtns(kasa,selKasa,'kasa')}</div>
      </div>
      <div>
        <label style="font-size:12px;font-weight:700;color:var(--mut)">YUK TIPI</label>
        <div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:6px">${tagBtns(yuk,selYuk,'yuk')}</div>
      </div>
      <div>
        <label style="font-size:12px;font-weight:700;color:var(--mut)">TELEFON</label>
        <input id="ef-tel" value="${escapeHtml(tel)}" style="width:100%;margin-top:4px;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg);color:var(--tx)">
      </div>
      <div>
        <label style="font-size:12px;font-weight:700;color:var(--mut)">ACIKLAMA</label>
        <textarea id="ef-aciklama" rows="3" style="width:100%;margin-top:4px;padding:8px;border:1px solid var(--border);border-radius:8px;font-size:13px;background:var(--bg);color:var(--tx);resize:vertical">${escapeHtml(ship.aciklama||'')}</textarea>
      </div>
      <div style="display:flex;gap:8px;margin-top:4px">
        <button onclick="saveEdit()" style="flex:1;padding:10px;background:var(--ok);color:#fff;border-radius:10px;font-weight:700;font-size:14px">Kaydet</button>
        <button onclick="closeEdit()" style="flex:1;padding:10px;background:var(--mut);color:#fff;border-radius:10px;font-weight:700;font-size:14px">Iptal</button>
      </div>
    </div>
  </div>
</div>`;
  const div = document.createElement('div');
  div.id = 'edit-root';
  div.innerHTML = html;
  document.body.appendChild(div);

  // il/ilce güncelleme
  window._ilceMap = ilceMap;
}

function _updateIlce(side){
  const ilSel = $('ef-'+side+'-il');
  const ilceSel = $('ef-'+side+'-ilce');
  if(!ilSel||!ilceSel) return;
  const il = ilSel.value;
  const list = (window._ilceMap||{})[il]||[];
  ilceSel.innerHTML = list.map(x=>`<option value="${x}">${x}</option>`).join('');
}

function _swapLoc(){
  const nIl=$('ef-n-il'), nIlce=$('ef-n-ilce'), yIl=$('ef-y-il'), yIlce=$('ef-y-ilce');
  const tmp1=nIl.value, tmp2=nIlce.value;
  nIl.value=yIl.value; _updateIlce('n'); nIlce.value=yIlce.value;
  yIl.value=tmp1; _updateIlce('y'); yIlce.value=tmp2;
}

function _toggleTag(btn){
  btn.classList.toggle('tag-on');
}

function _getTagVals(field){
  return [...document.querySelectorAll(`.tag-toggle.tag-on[data-field="${field}"]`)].map(b=>b.dataset.val);
}

async function saveEdit(){
  const updates = {
    isim: $('ef-isim').value.trim(),
    nereden_il: $('ef-n-il').value,
    nereden_ilce: $('ef-n-ilce').value,
    nereye_il: $('ef-y-il').value,
    nereye_ilce: $('ef-y-ilce').value,
    arac_tipi: _getTagVals('arac'),
    kasa_tipi: _getTagVals('kasa'),
    yuk_tipi: _getTagVals('yuk'),
    telefon: $('ef-tel').value.split(/[,\\s]+/).map(t=>t.replace(/\\D/g,'')).filter(Boolean),
    aciklama: $('ef-aciklama').value.trim(),
  };
  const url = '/api/unprocessed/'+encodeURIComponent(_editMsgId)+'/shipment/'+_editShipIdx;
  const d = await api(url, {method:'PATCH', body:JSON.stringify(updates)});
  if(d&&d.ok){
    // Local state güncelle
    const msg = _unprocessedMsgs.find(m=>m.message_id===_editMsgId);
    if(msg && msg.shipments && msg.shipments[_editShipIdx]) Object.assign(msg.shipments[_editShipIdx], updates);
    closeEdit();
    _renderCurrentMsg();
    toast('Sevkiyat guncellendi');
  } else if(d) toast(d.error||'Hata',true);
}

function closeEdit(){
  const r = document.getElementById('edit-root');
  if(r) r.remove();
}
</script>
</body>
</html>"""


@app.route("/")
def index():
    """Mobil tek sayfa arayüzü döner."""
    return Response(INDEX_HTML, mimetype="text/html")


if __name__ == "__main__":
    _cleanup_old_unprocessed()  # Başlangıçta eski kayıtları temizle
    _start_bg_loader()          # Dosyayı arka planda belleğe yükle
    _refresh_status_cache()     # PM2 durumunu arka planda cache'le
    _schedule_daily_cleanup()
    _start_auto_approve()       # Sunucu tarafı oto onay (son 1 saat, 3 sn'de bir)
    port = int(os.getenv("ADMIN_PANEL_PORT", "8080"))
    logger.info(f"🌐 Mobil Yönetim Paneli başlıyor: 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
