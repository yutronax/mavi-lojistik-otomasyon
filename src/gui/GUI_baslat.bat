@echo off
chcp 65001 >nul
echo ========================================
echo   LOJİSTİK YÖNETİM SİSTEMİ (GUI)
echo ========================================
echo.
echo GUI başlatılıyor...
echo.

cd /d "%~dp0\.."
python gui\masaustu_uygulama.py

echo.
echo ========================================
echo   GUI kapatıldı
echo ========================================
pause

