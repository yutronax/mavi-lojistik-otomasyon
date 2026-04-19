#!/bin/bash
# Mavi Lojistik - Otonom Sunucu Durdurma Betiği

echo "------------------------------------------"
echo "🛑 Mavi Lojistik Sunucusu Durduruluyor..."
echo "------------------------------------------"

# PM2 üzerindeki süreci durdur
pm2 stop mavi-lojistik-server

echo ""
echo "✅ İşlem tamamlandı. Mevcut durum:"
pm2 status
echo "------------------------------------------"
