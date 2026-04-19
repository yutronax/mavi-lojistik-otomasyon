@echo off
rem Mavi Lojistik - Otonom Sunucu Durdurma Betigi (Windows)

echo ------------------------------------------
echo 🛑 Mavi Lojistik Sunucusu Durduruluyor...
echo ------------------------------------------

rem PM2 uzerindeki sureci durdur
call pm2 stop mavi-lojistik-server

echo.
echo ✅ Islem tamamlandi. Mevcut durum:
call pm2 status
echo ------------------------------------------
pause
