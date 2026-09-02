module.exports = {
  apps : [{
    name: "mavi-lojistik-server",
    script: "vps_main.py",
    interpreter: "./.venv/bin/python3",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '700M',
    env: {
      NODE_ENV: "production",
      PYTHONUNBUFFERED: "1"
    },
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/pm2_error.log",
    out_file: "logs/pm2_out.log",
    merge_logs: true
  },{
    name: "mavi-admin-panel",
    script: "src/api/admin_panel.py",
    interpreter: "./.venv/bin/python3",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '700M',
    env: {
      PYTHONUNBUFFERED: "1"
    },
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "logs/panel_error.log",
    out_file: "logs/panel_out.log",
    merge_logs: true
  },{
    // Saga epic #46 (baileys-uretim-gecisi): Baileys sidecar, vps_main.py'nin
    // 8080 portunda dinleyen /baileys-webhook'una mesaj gönderir.
    // auth_info_baileys/ klasörü ÜRETIM numarasının oturumunu tutar —
    // bu klasör silinirse/kaybolursa yeniden QR taratmak gerekir.
    name: "mavi-baileys-bridge",
    script: "bridge.js",
    interpreter: "node",
    cwd: "./sidecar",
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '300M',
    env: {
      NODE_ENV: "production",
      WEBHOOK_URL: "http://127.0.0.1:8090/baileys-webhook"
    },
    log_date_format: "YYYY-MM-DD HH:mm:ss",
    error_file: "../logs/baileys_bridge_error.log",
    out_file: "../logs/baileys_bridge_out.log",
    merge_logs: true
  }]
}
