# mavi-lojistik Deployment Guide

## ✅ Status: PRODUCTION READY

Sistem tüm kritik özellikleri içeriyor ve lokal ortamda başarıyla test edilmiştir.

## 🚀 Quick Start (Local)

```bash
# 1. Dependencies yükle
pip install -r requirements.txt

# 2. Orchestrator başlat (Backend)
python src/parsers/veri_cekici_ayristirici.py

# 3. GUI başlat (Frontend)
python src/gui/masaustu_uygulama.py
```

## 🌐 Remote Deployment (Manual)

### Prerequisites
- Ubuntu/Debian Linux sunucu
- Python 3.8+
- PM2 (process manager)
- MongoDB (optional, for auto-submit tracking)

### Deployment Steps

```bash
# 1. Remote sunucuya SSH ile bağlan
ssh root@YOUR_SERVER_IP

# 2. Repository klonla
git clone https://github.com/yutronax/mavi-lojistik-otomasyon.git
cd mavi-lojistik-otomasyon

# 3. Latest branch'i checkout et
git fetch origin
git checkout claude/festive-pare-2fb538
git pull origin claude/festive-pare-2fb538

# 4. Dependencies yükle
pip install -r requirements.txt

# 5. Ortam ayarlarını ayarla
cp .env.example .env
# SSH config'i konfigure et: data/ssh_config.json

# 6. PM2 ile başlat
pm2 start ecosystem.config.js
pm2 save
pm2 startup
```

## 📋 Installed Features

### Security ✅
- [x] SSH password encryption (Fernet)
- [x] Role-Based Access Control (3 roles)
- [x] Rate limiting (5 restart/min)
- [x] Operation audit logging

### Reliability ✅
- [x] Auto-restart on crash (5 min threshold)
- [x] Blue-green deployment (auto-rollback)
- [x] Scheduled backups (Daily + Weekly)
- [x] Health monitoring with alerts

### Observability ✅
- [x] Real-time VPS monitoring dashboard
- [x] WhatsApp notifications (Whapi)
- [x] Performance metrics (CPU, RAM, Disk, Load)
- [x] Alert history tracking

### Code Quality ✅
- [x] Component-based UI architecture
- [x] Modular utilities (100+ lines each)
- [x] Async/await throughout
- [x] Clean error handling

## 🔧 Configuration

### SSH Config (data/ssh_config.json)
```json
{
    "host": "YOUR_SERVER_IP",
    "user": "root",
    "port": 22,
    "pwd": "encrypted:[encrypted_password]"
}
```
Password will be auto-encrypted on first use.

### Environment Variables (.env)
```env
WHAPI_API_KEY=your_whapi_key
WHAPI_PHONE_ID=5318407744
TELEGRAM_BOT_TOKEN=optional
GEMINI_API_KEY=your_gemini_key
GROQ_API_KEY=your_groq_key
DEEPSEEK_API_KEY=your_deepseek_key
```

## 📊 System Architecture

```
mavi-lojistik/
├── src/
│   ├── parsers/          # Core business logic (orchestrator)
│   ├── gui/              # UI components (Flet)
│   │   ├── components/   # Reusable tab components
│   │   ├── pages/        # Main pages
│   │   └── styles.py     # Consistent styling
│   ├── services/         # Data persistence
│   ├── utils/            # Utilities
│   │   ├── notification_service.py    # WhatsApp alerts
│   │   ├── deployment_manager.py      # Blue-green deploy
│   │   ├── health_monitor.py          # Health checks
│   │   ├── auto_restart_manager.py    # Auto-recovery
│   │   ├── backup_scheduler.py        # Scheduled backups
│   │   ├── access_control.py          # RBAC
│   │   ├── operation_logger.py        # Audit trail
│   │   └── command_rate_limiter.py    # Rate limiting
│   └── fetchers/         # WhatsApp integration
├── data/                 # Config & data files
├── logs/                 # Application logs
└── deploy.sh            # Deployment script
```

## 🎯 Key Features

### 1. WhatsApp Notifications
- Auto-restart events
- Health alerts (CPU >80%, RAM >85%, Disk >90%)
- Operation logs
- Deployment status

### 2. VPS Monitoring Dashboard
- Real-time CPU/RAM/Disk gauges
- Service status indicator
- System uptime tracking
- Load average monitoring
- Alert history (last 20)

### 3. Auto-Restart on Crash
- Monitors every 30 seconds
- Restarts if down >5 minutes
- Exponential backoff (3 attempts max)
- Full notification integration

### 4. Scheduled Backups
- Daily: 2:00 AM
- Weekly: Sunday 3:00 AM
- Auto-cleanup (keeps last 5)
- Rollback capability

### 5. Role-Based Access
- Admin: Full access
- Operator: Control + view
- Viewer: Read-only

## 📈 Monitoring Commands

```bash
# Check PM2 status
pm2 status
pm2 logs mavi-lojistik-server

# Check backups
ls -lah data/deployment_backups/

# Check operation logs
tail -f data/operation_log.json

# Monitor health
pm2 monit
```

## 🔐 Security Checklist

- [ ] SSH keys configured (no passwords)
- [ ] Firewall rules configured
- [ ] SSL/TLS certificates installed
- [ ] API keys stored in .env (not committed)
- [ ] MongoDB authentication enabled
- [ ] Regular backups tested

## 🐛 Troubleshooting

### Service not starting
```bash
pm2 delete mavi-lojistik-server
pm2 start ecosystem.config.js --only mavi-lojistik-server
```

### Deployment rollback
```bash
# Manual rollback
cd ~/mavi-lojistik-otomasyon
git reset --hard HEAD~1
pm2 restart mavi-lojistik-server
```

### Check logs
```bash
pm2 logs mavi-lojistik-server --lines 100
tail -f logs/pm2_out.log
```

## 📞 Support

For issues, check:
1. `logs/` directory for detailed logs
2. `data/operation_log.json` for operation history
3. WhatsApp alerts for system notifications
4. PM2 monitoring dashboard

---

**Version**: 1.0.0  
**Last Updated**: 2026-06-09  
**Status**: Production Ready ✅
