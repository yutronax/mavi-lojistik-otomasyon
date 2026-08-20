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
  }]
}
