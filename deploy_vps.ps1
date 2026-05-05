
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
$REMOTE_DIR = "~/mavi-lojistik"

Write-Host "--- VPS YÜKLEME BAŞLATILDI ($IP) ---" -ForegroundColor Cyan

# 1. Projeyi paketle (Hız için)
# Gereksiz dosyaları hariç tut (data, logs, venv, git, tar.gz)
Write-Host "[1/4] Dosyalar paketleniyor..."
tar --format=ustar --exclude="data" --exclude="logs" --exclude="venv" --exclude=".venv" --exclude=".git" --exclude="__pycache__" --exclude="*.tar.gz" --exclude="dist" --exclude="build" -czf project.tar.gz .

# 2. Sunucuda klasörü oluştur ve dosyayı gönder
Write-Host "[2/4] Sunucuya aktarılıyor..."
ssh "${USER}@${IP}" "mkdir -p ${REMOTE_DIR}/logs"
scp project.tar.gz "${USER}@${IP}:${REMOTE_DIR}/"

# 3. Sunucuda paketi aç ve temizle
Write-Host "[3/4] Sunucuda dosyalar güncelleniyor..."
ssh "${USER}@${IP}" "cd ${REMOTE_DIR} && tar -xzf project.tar.gz && rm project.tar.gz"

Write-Host "[4/4] Bağımlılıklar güncelleniyor ve servisler başlatılıyor..."
ssh "${USER}@${IP}" "cd ${REMOTE_DIR} && python3 -m venv .venv && ./.venv/bin/pip install --upgrade pip && ./.venv/bin/pip install -r requirements.txt && pm2 restart all || pm2 start ecosystem.config.js"

# Temizlik
Remove-Item project.tar.gz
Write-Host "--- YÜKLEME BAŞARIYLA TAMAMLANDI! ---" -ForegroundColor Green
