@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo   Mavi Lojistik - Otomatik Kurulum
echo ========================================
echo.

REM 1. Python Kontrolü
echo [1/5] Python kontrol ediliyor...
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [HATA] Python bulunamadi!
    echo Lutfen Python 3.10 veya uzeri bir surum yukleyin: https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Python bulundu.
python --version
echo.

REM 2. Sanal Ortam (venv) Olusturma
echo [2/5] Sanal ortam hazirlaniyor (.venv)...
if not exist ".venv" (
    python -m venv .venv
    echo [OK] .venv olusturuldu.
) else (
    echo [BILGI] .venv zaten mevcut, devam ediliyor.
)
echo.

REM 3. Bagimliliklarin Yuklenmesi
echo [3/5] Kutuphaneler yukleniyor (Bu islem internet hizina gore surebilir)...
call .venv\Scripts\activate.bat
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if %errorlevel% neq 0 (
    echo [HATA] Kutuphaneler yuklenirken bir sorunolustu.
    pause
    exit /b 1
)
echo [OK] Tum kutuphaneler yuklendi.
echo.

REM 4. .env Dosyasi Kontrolu
echo [4/5] Ayarlar kontrol ediliyor (.env)...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env
        echo [BILGI] .env dosyasi ornekten olusturuldu. Lutfen icindeki API anahtarlarini kontrol edin.
    ) else (
        echo [UYARI] .env dosyasi bulunamadi! Uygulama calismayabilir.
    )
) else (
    echo [OK] .env dosyasi mevcut.
)
echo.

REM 5. Uygulama Derleme (EXE ve Kisayol)
echo [5/5] Uygulama derleniyor ve masaustu kisayollari olusturuluyor...
echo (Bu islem ilk seferde 1-2 dakika surebilir)
echo.
call build.bat

echo.
echo ========================================
echo         KURULUM TAMAMLANDI!
echo ========================================
echo.
echo 1. Masaustunuzdeki 'MaviLojistik' kisayolunu kullanabilirsiniz.
echo 2. 'TanimlamaMerkezi' kisayolu ile yuk ve sehir tanimlamalarini yapabilirsiniz.
echo.
echo Ayarlar icin .env dosyasini kontrol etmeyi unutmayin.
echo.
pause
