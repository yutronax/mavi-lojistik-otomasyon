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
from functools import wraps

from flask import Flask, request, jsonify, Response

# Proje kök dizini (src/api/admin_panel.py → 2 üst klasör)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

SERVICE_NAME = "mavi-lojistik-server"
BLACKLIST_PATH = os.path.join(PROJECT_ROOT, "data", "blacklist.json")
GROUPS_PATH = os.path.join(PROJECT_ROOT, "data", "chat_groups.json")
MESSAGES_PATH = os.path.join(PROJECT_ROOT, "data", "live_messages.json")
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")
LOG_PATHS = [
    os.path.join(PROJECT_ROOT, "logs", "pm2_out.log"),
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

@app.route("/api/status")
@require_auth
def status():
    """Servis (PM2) durumu + sistem metriklerini döner."""
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
    # Sistem metrikleri (/proc/meminfo + disk + loadavg)
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
    return jsonify(result)


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
    for path in LOG_PATHS:
        if os.path.exists(path):
            try:
                result = subprocess.run(
                    ["tail", "-n", str(lines), path],
                    capture_output=True, text=True, timeout=10, errors="replace"
                )
                if result.stdout.strip():
                    chunks.append(f"━━━ {os.path.basename(path)} ━━━")
                    chunks.append(result.stdout.strip())
            except Exception as e:
                chunks.append(f"{path} okunamadı: {e}")
    return jsonify({"logs": "\n".join(chunks) or "Log bulunamadı."})



# ---------------- API: Mesajlar ----------------

@app.route("/api/messages", methods=["GET"])
@require_auth
def messages_get():
    """Son WhatsApp mesajlarını (data/live_messages.json) en yeniden eskiye döner."""
    limit = min(int(request.args.get("limit", 50)), 200)
    try:
        with open(MESSAGES_PATH, "r", encoding="utf-8") as f:
            items = json.load(f)
    except Exception:
        items = []
    items = sorted(items, key=lambda m: m.get("timestamp", 0), reverse=True)
    return jsonify({"messages": items[:limit]})


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

@app.route("/api/groups/available", methods=["GET"])
@require_auth
def groups_available():
    """Whapi'dan tüm grupları çekip kayıtlı olanları işaretler."""
    token = os.getenv("WHATSAPP_TOKEN", "")
    try:
        import urllib.request
        req = urllib.request.Request(
            "https://gate.whapi.cloud/groups?count=100",
            headers={"Authorization": f"Bearer {token}"}
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode())
        all_groups = data.get("groups", [])
        saved_ids = {g["id"] for g in _load_groups()}
        result = [{"id": g["id"], "name": g.get("name",""), "saved": g["id"] in saved_ids}
                  for g in all_groups if g.get("type") == "group"]
        result.sort(key=lambda x: (not x["saved"], x["name"]))
        return jsonify({"groups": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
    """Numara ekler; sadece rakam, 10-11 hane doğrulaması yapar."""
    body = request.get_json(silent=True) or {}
    num = "".join(c for c in str(body.get("number", "")) if c.isdigit())
    if len(num) == 10:
        num = "0" + num
    if len(num) != 11 or not num.startswith("0"):
        return jsonify({"error": "Geçersiz numara (05XXXXXXXXX bekleniyor)"}), 400
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
header{padding:16px 20px;background:var(--card);border-bottom:1px solid var(--border);display:flex;justify-content:space-between;align-items:center}
header h1{font-size:16px;font-weight:700}
.dot{width:9px;height:9px;border-radius:50%;display:inline-block;margin-right:6px}
.card{background:var(--card);border:1px solid var(--border);border-radius:14px;padding:16px;margin:16px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}
.stat{text-align:center;padding:14px 8px;background:#fafafa;border:1px solid var(--border);border-radius:10px}
.stat b{font-size:20px;display:block}
.stat span{color:var(--mut);font-size:12px}
button{border:0;border-radius:10px;padding:13px;font-size:15px;font-weight:600;color:#fff;width:100%;cursor:pointer}
.b-ok{background:var(--ok)}.b-err{background:var(--err)}.b-warn{background:var(--warn)}.b-acc{background:var(--acc)}
.row{display:flex;gap:8px;margin-top:10px}
input{width:100%;padding:12px;border-radius:10px;border:1px solid var(--border);background:#fff;color:var(--tx);font-size:15px}
pre{background:#0f172a;color:#d1d5db;padding:10px;border-radius:10px;font-size:11px;overflow:auto;max-height:60vh;white-space:pre-wrap;word-break:break-all}
.bl-item{display:flex;justify-content:space-between;align-items:center;padding:9px 4px;border-bottom:1px solid var(--border);font-size:14px}
.bl-item button{width:auto;padding:6px 12px;font-size:12px}
label{color:var(--mut);font-size:12px;display:block;margin:10px 0 4px}
#toast{position:fixed;top:16px;left:50%;transform:translateX(-50%);background:var(--acc);color:#fff;padding:10px 18px;border-radius:10px;font-size:14px;z-index:20;transition:.3s;opacity:0}
.login-wrap{max-width:340px;margin:25vh auto;padding:0 16px;text-align:center}
.login-wrap h2{margin-bottom:18px}
@media (max-width:768px){
  .sidebar{position:fixed;left:0;top:0;bottom:0;z-index:15}
  .sidebar.collapsed{width:0;border-right:0}
  .grid{grid-template-columns:repeat(2,1fr)}
}
</style>
</head>
<body>

<div id="login" class="login-wrap">
  <h2>🚛 Mavi Lojistik</h2>
  <input id="pwd" type="password" placeholder="Panel şifresi" autocomplete="current-password">
  <div style="height:10px"></div>
  <button class="b-acc" onclick="doLogin()">Giriş</button>
</div>

<div id="app" class="hide">
<aside class="sidebar" id="sidebar">
  <div class="brand"><span class="logo">🚛</span><span class="label">Mavi Lojistik</span></div>
  <button class="collapse-btn" onclick="toggleSidebar()" title="Daralt/Genişlet">☰</button>
  <nav>
    <button class="act" onclick="tab('status',this)"><span class="ic">📊</span><span class="label">Durum</span></button>
    <button onclick="tab('msg',this);loadMessages()"><span class="ic">💬</span><span class="label">Mesajlar</span></button>
    <button onclick="tab('grp',this);loadGroups()"><span class="ic">👥</span><span class="label">Gruplar</span></button>
    <button onclick="tab('logs',this);loadLogs()"><span class="ic">📜</span><span class="label">Loglar</span></button>
    <button onclick="tab('bl',this);loadBl()"><span class="ic">🚫</span><span class="label">Kara Liste</span></button>
    <button onclick="tab('set',this);loadSet()"><span class="ic">⚙️</span><span class="label">Ayarlar</span></button>
  </nav>
</aside>
<main>
<header><h1>Mavi Lojistik Panel</h1><span id="svcdot"><span class="dot" style="background:var(--mut)"></span><span id="svctxt">...</span></span></header>

<div id="tab-status">
  <div class="card">
    <div class="grid">
      <div class="stat"><b id="s-cpu">–</b><span>CPU %</span></div>
      <div class="stat"><b id="s-mem">–</b><span>Servis RAM (MB)</span></div>
      <div class="stat"><b id="s-ram">–</b><span>Sunucu RAM %</span></div>
      <div class="stat"><b id="s-disk">–</b><span>Disk %</span></div>
    </div>
    <div class="row">
      <button class="b-ok" onclick="svc('start')">▶ Başlat</button>
      <button class="b-warn" onclick="svc('restart')">⟳ Restart</button>
      <button class="b-err" onclick="if(confirm('Servis durdurulsun mu?'))svc('stop')">■ Durdur</button>
    </div>
    <p id="s-extra" style="color:var(--mut);font-size:12px;margin-top:10px"></p>
  </div>
</div>

<div id="tab-msg" class="hide">
  <div class="card">
    <div class="row" style="margin:0 0 10px">
      <button class="b-acc" onclick="loadMessages()">⟳ Yenile</button>
    </div>
    <div id="msg-list"><p style="color:var(--mut);font-size:13px">Yükleniyor...</p></div>
  </div>
</div>

<div id="tab-grp" class="hide">
  <div class="card">
    <div class="row" style="margin:0 0 10px">
      <button class="b-acc" onclick="loadGroups()">⟳ Kayıtlı Gruplar</button>
      <button class="b-warn" onclick="loadAvailableGroups()">🔍 Whapi'dan Getir</button>
    </div>
    <p id="grp-count" style="color:var(--mut);font-size:12px;margin:0 0 4px"></p>
    <div id="grp-list"></div>
    <div id="grp-available" class="hide" style="margin-top:14px">
      <label>Whapi Grupları (kayıtlı olmayanlar önce)</label>
      <div id="grp-available-list"></div>
    </div>
  </div>
</div>

<div id="tab-logs" class="hide">
  <div class="card">
    <div class="row" style="margin:0 0 10px">
      <button class="b-acc" onclick="loadLogs()">⟳ Yenile</button>
    </div>
    <pre id="logbox">Yükleniyor...</pre>
  </div>
</div>

<div id="tab-bl" class="hide">
  <div class="card">
    <div class="row" style="margin:0">
      <input id="bl-new" placeholder="05XXXXXXXXX" inputmode="numeric">
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
      <button class="b-acc" onclick="saveSet(false)">Kaydet</button>
      <button class="b-warn" onclick="saveSet(true)">Kaydet + Restart</button>
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

function toggleSidebar(){
  const sb = $('sidebar');
  sb.classList.toggle('collapsed');
  localStorage.setItem('sbCollapsed', sb.classList.contains('collapsed') ? '1' : '0');
}
(function initSidebar(){
  const stored = localStorage.getItem('sbCollapsed');
  const collapsed = stored !== null ? stored === '1' : window.innerWidth < 768;
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
  ['status','msg','grp','logs','bl','set'].forEach(t=>$('tab-'+t).classList.add('hide'));
  $('tab-'+name).classList.remove('hide');
  document.querySelectorAll('nav button').forEach(b=>b.classList.remove('act'));
  if(btn)btn.classList.add('act');
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

async function loadMessages(){
  $('msg-list').innerHTML = '<p style="color:var(--mut);font-size:13px">Yükleniyor...</p>';
  const d = await api('/api/messages?limit=50'); if(!d) return;
  if(!d.messages.length){$('msg-list').innerHTML = '<p style="color:var(--mut);font-size:13px">Mesaj bulunamadı.</p>'; return;}
  $('msg-list').innerHTML = d.messages.map(m => `
    <div class="bl-item" style="display:block">
      <div style="display:flex;justify-content:space-between;color:var(--mut);font-size:12px">
        <span>${escapeHtml(m.group)}</span><span>${escapeHtml(m.time)}</span>
      </div>
      <div style="font-weight:600;font-size:13px;margin:2px 0">${escapeHtml(m.sender)}</div>
      <div style="font-size:13px;white-space:pre-wrap">${escapeHtml(m.body)}</div>
    </div>`).join('');
}

async function loadGroups(){
  $('grp-available').classList.add('hide');
  const d = await api('/api/groups'); if(!d) return;
  $('grp-count').textContent = `Kayıtlı ${d.groups.length} grup`;
  $('grp-list').innerHTML = d.groups.map(g =>
    `<div class="bl-item"><span>${escapeHtml(g.name)}</span><button class="b-err" onclick="grpDel('${g.id}')">Sil</button></div>`).join('');
}

async function loadAvailableGroups(){
  $('grp-available').classList.remove('hide');
  $('grp-available-list').innerHTML = '<p style="color:var(--mut);font-size:13px">Sunucudan çekiliyor...</p>';
  const d = await api('/api/groups/available'); if(!d) return;
  if(d.error){$('grp-available-list').innerHTML = `<p style="color:var(--err);font-size:13px">${escapeHtml(d.error)}</p>`; return;}
  $('grp-available-list').innerHTML = d.groups.map(g => `
    <div class="bl-item">
      <span>${escapeHtml(g.name)}${g.saved ? ' <span style="color:var(--ok)">(kayıtlı)</span>' : ''}</span>
      ${g.saved ? '' : `<button class="b-ok" onclick="grpAdd('${g.id}','${escapeHtml(g.name).replace(/'/g,"\\'")}')">Ekle</button>`}
    </div>`).join('');
}

async function grpAdd(id, name){
  const d = await api('/api/groups',{method:'POST',body:JSON.stringify({id,name})});
  if(d&&d.ok){toast('Eklendi ✓');loadGroups();loadAvailableGroups();} else if(d) toast(d.error,true);
}

async function grpDel(id){
  if(!confirm('Bu grup silinsin mi?'))return;
  const d = await api('/api/groups/'+encodeURIComponent(id),{method:'DELETE'});
  if(d&&d.ok){toast('Silindi ✓');loadGroups();} else if(d) toast(d.error,true);
}

async function loadLogs(){
  $('logbox').textContent='Yükleniyor...';
  const d = await api('/api/logs?lines=150'); if(!d) return;
  $('logbox').textContent = d.logs;
  $('logbox').scrollTop = $('logbox').scrollHeight;
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
}
if(TOK){ api('/api/status').then(d=>{ if(d) start(); }); }
$('pwd').addEventListener('keydown',e=>{if(e.key==='Enter')doLogin();});
</script>
</body>
</html>"""


@app.route("/")
def index():
    """Mobil tek sayfa arayüzü döner."""
    return Response(INDEX_HTML, mimetype="text/html")


if __name__ == "__main__":
    port = int(os.getenv("ADMIN_PANEL_PORT", "8080"))
    logger.info(f"🌐 Mobil Yönetim Paneli başlıyor: 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
