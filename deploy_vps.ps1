
# Mavi Lojistik VPS Deployment Script
# VPS'teki /opt/mavi-lojistik zaten bir git reposu (PM2 servisleri buradan
# çalışıyor) - bu script tar/scp ile dosya KOPYALAMAZ, git pull ile günceller.
# (2026-09-02: önceki tar/scp sürümü ~/mavi-lojistik'e (root'un ev dizini)
# yüklüyordu ama PM2 servisleri /opt/mavi-lojistik'ten çalışıyordu - bu
# yüzden hiçbir deploy gerçek üretime yansımıyordu. Kök neden bulunup
# git-pull modeline geçirildi, gerçek VPS kurulumuyla artık tutarlı.)

$configPath = "data/ssh_config.json"
if (-not (Test-Path $configPath)) {
    Write-Host "Hata: ssh_config.json bulunamadı!" -ForegroundColor Red
    exit 1
}

$config = Get-Content $configPath | ConvertFrom-Json
$IP = $config.host
$USER = $config.user
$PORT = if ($config.port) { $config.port } else { 22 }
$REMOTE_DIR = "/opt/mavi-lojistik"

Write-Host "--- VPS GUNCELLEME BASLATILDI ($IP`:$PORT -> $REMOTE_DIR) ---" -ForegroundColor Cyan

# data/ klasörü git'te tracked (canlı sevkiyat verisi) ve sürekli üretim
# tarafından yazılıyor - her deploy'da yerel değişiklikleri stash'leyip
# pull sonrası geri koyuyoruz. Stash pop çakışırsa (aynı dosyaya deploy
# ile eş zamanlı yazım) script BAŞARISIZ olmaz - canlı veri stash'te
# güvende kalır, sadece uyarı basılır, elle "git stash list" ile kontrol
# edilmesi gerekir.
$remoteScript = @"
set -e
cd $REMOTE_DIR
echo '[1/4] Yerel degisiklikler (canli veri) stash leniyor...'
git stash push -u -m "auto-deploy-`$(date +%Y%m%d-%H%M%S)" || true
echo '[2/4] main cekiliyor...'
git fetch origin main
git checkout main
git merge origin/main --ff-only
echo '[3/4] Bagimliliklar guncelleniyor...'
[ -d venv ] && [ ! -e .venv ] && ln -sfn venv .venv
[ -d .venv ] || python3 -m venv .venv
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt
cd sidecar && npm install --omit=dev --silent && cd ..
echo '[4/4] Servisler yeniden baslatiliyor...'
pm2 startOrReload ecosystem.config.js
git stash pop || echo 'UYARI: stash pop cakisti - canli veri stash tada guvende, elle "git stash list" ile kontrol edin.'
"@

ssh -p $PORT "${USER}@${IP}" $remoteScript
if ($LASTEXITCODE -ne 0) {
    Write-Host "--- HATA: Uzak sunucuda deploy adimlari basarisiz oldu (yukaridaki cikti) ---" -ForegroundColor Red
    exit 1
}

Write-Host "--- GUNCELLEME BASARIYLA TAMAMLANDI! ---" -ForegroundColor Green
