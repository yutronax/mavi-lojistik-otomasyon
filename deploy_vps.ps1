
# Mavi Lojistik VPS Deployment Script
# Bu script yereldeki güncel dosyaları VPS'e yükler.

$configPath = "data/ssh_config.json"
if (-not (Test-Path $configPath)) {
    Write-Host "Hata: ssh_config.json bulunamadı!" -ForegroundColor Red
    exit
}

$config = Get-Content $configPath | ConvertFrom-Json
$IP = $config.host
$USER = $config.user
$PORT = if ($config.port) { $config.port } else { 22 }
$REMOTE_DIR = "~/mavi-lojistik"

Write-Host "--- VPS YÜKLEME BAŞLATILDI ($IP`:$PORT) ---" -ForegroundColor Cyan

# 1. Projeyi paketle (Hız için)
# Gereksiz dosyaları hariç tut (data, logs, venv, git, tar.gz)
# node_modules HARİÇ TUTULUR: Windows'ta derlenmiş native modüller Linux
# VPS'te çalışmaz - sidecar/node_modules VPS'te ayrıca npm install ile
# kurulmalı (adım 4'te yapılıyor).
Write-Host "[1/4] Dosyalar paketleniyor..."
tar --format=ustar --exclude="data" --exclude="logs" --exclude="venv" --exclude=".venv" --exclude=".git" --exclude="__pycache__" --exclude="*.tar.gz" --exclude="dist" --exclude="build" --exclude="node_modules" -czf project.tar.gz .

# 2. Sunucuda klasörü oluştur ve dosyayı gönder
Write-Host "[2/4] Sunucuya aktarılıyor..."
ssh -p $PORT "${USER}@${IP}" "mkdir -p ${REMOTE_DIR}/logs"
if ($LASTEXITCODE -ne 0) { Write-Host "--- HATA: SSH bağlantısı kurulamadı (port $PORT) ---" -ForegroundColor Red; exit 1 }
scp -P $PORT project.tar.gz "${USER}@${IP}:${REMOTE_DIR}/"
if ($LASTEXITCODE -ne 0) { Write-Host "--- HATA: Dosya transferi başarısız ---" -ForegroundColor Red; exit 1 }

# 3. Sunucuda paketi aç ve temizle
Write-Host "[3/4] Sunucuda dosyalar güncelleniyor..."
ssh -p $PORT "${USER}@${IP}" "cd ${REMOTE_DIR} && tar -xzf project.tar.gz && rm project.tar.gz"
if ($LASTEXITCODE -ne 0) { Write-Host "--- HATA: Sunucuda paket açma başarısız ---" -ForegroundColor Red; exit 1 }

Write-Host "[4/4] Bağımlılıklar güncelleniyor ve servisler başlatılıyor..."
# Baileys epic #42-46 (2026-09-01): sidecar/ Node.js kodu için npm install
# eklendi - node.js/npm VPS'te kurulu olmalı.
ssh -p $PORT "${USER}@${IP}" "cd ${REMOTE_DIR} && python3 -m venv .venv && ./.venv/bin/pip install --upgrade pip && ./.venv/bin/pip install -r requirements.txt && cd sidecar && npm install --omit=dev && cd .. && pm2 restart all || pm2 start ecosystem.config.js"
if ($LASTEXITCODE -ne 0) { Write-Host "--- HATA: Bağımlılık kurulumu/servis başlatma başarısız ---" -ForegroundColor Red; exit 1 }

# Temizlik
Remove-Item project.tar.gz
Write-Host "--- YÜKLEME BAŞARIYLA TAMAMLANDI! ---" -ForegroundColor Green
