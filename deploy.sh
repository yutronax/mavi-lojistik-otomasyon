#!/bin/bash
# Remote Deployment Script for mavi-lojistik

set -e

HOST="209.38.223.10"
USER="root"
PROJECT_DIR="~/mavi-lojistik-otomasyon"
BRANCH="claude/festive-pare-2fb538"

echo "🚀 Deploying to $HOST..."
echo ""

ssh -o StrictHostKeyChecking=no $USER@$HOST << 'EOF'

echo "📦 Starting deployment..."

# Navigate to project
cd ~/mavi-lojistik-otomasyon || exit 1

# Stop PM2 processes (if running)
echo "⏸️ Stopping services..."
pm2 stop mavi-lojistik-server 2>/dev/null || true
pm2 stop mavi-web-server 2>/dev/null || true
sleep 2

# Update code
echo "📥 Fetching latest code..."
git fetch origin
git checkout $BRANCH
git pull origin $BRANCH

# Install/update dependencies
echo "📦 Installing dependencies..."
pip install -q -r requirements.txt 2>/dev/null || pip install -q aiohttp cryptography apscheduler flet nest-asyncio paramiko

# Create necessary directories
echo "📁 Creating directories..."
mkdir -p data logs .claude
chmod 700 .claude

# Start services with PM2
echo "🔄 Starting services..."
pm2 start ecosystem.config.js --only mavi-lojistik-server 2>/dev/null || echo "Note: PM2 ecosystem not found, services may need manual start"

# Check status
echo ""
echo "✅ Deployment completed!"
echo ""
echo "📊 Service Status:"
pm2 status 2>/dev/null || echo "PM2 status unavailable"

EOF

echo ""
echo "✅ Remote deployment complete!"
echo "🌐 System deployed to: $HOST"
