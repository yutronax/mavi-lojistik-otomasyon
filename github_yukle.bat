@echo off
chcp 65001 >nul
echo Mavi Lojistik Otomasyon - GitHub Yukleme Araci v2
echo.

:: Git kontrolu
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [HATA] Git bulunamadi! Lutfen Git'i kurdugunuzdan emin olun.
    pause
    exit /b
)

:: Kullanici bilgileri kontrolu ve girisi
echo [ONEMLI] Git islemleri icin kimlik bilgileriniz gerekiyor.
echo GitHub email adresinizi girin (ornek: email@adresiniz.com):
set /p git_email="Email: kuyusuzyusuf123@gmail.com"

echo.
echo Adinizi Soyadinizi girin:
set /p git_name="Isim: yusufcinar"

echo.
echo [BILGI] Git ayarlari yapiliyor...
git config user.email "kuyusuuzyusuf123@gmail.com"
git config user.name "yutronax"

echo.
echo [BILGI] Git deposu hazirlaniyor...
git init

echo [BILGI] Dosyalar ekleniyor...
git add .

echo [BILGI] Kayit olusturuluyor...
git commit -m "Ilk kurulum: Mavi Lojistik Otomasyonu"

echo [BILGI] Ana dal ayarlaniyor...
git branch -M main

echo [BILGI] Uzak sunucu baglantisi guncelleniyor...
:: Varsa eskini silip yenisini ekliyoruz ki hata vermesin
git remote remove origin >nul 2>&1
git remote add origin https://github.com/yutronax/mavi-lojistik-otomasyon.git

echo.
echo [BILGI] Kodlar GitHub'a gonderiliyor...
echo [NOT] Acilan pencerede GitHub kullanici adi ve sifrenizi girmeniz istenebilir.
git push -u origin main

if %errorlevel% neq 0 (
    echo.
    echo [HATA] Gonderim basarisiz oldu.
    echo Lutfen suan acik olan terminaldeki hatalari okuyun.
) else (
    echo.
    echo [BASARILI] Projeniz https://github.com/yutronax/mavi-lojistik-otomasyon adresine yuklendi!
)

pause
