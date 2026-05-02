@echo off
setlocal
cd /d "%~dp0"

echo ========================================
echo Mavi Lojistik - Build Script
echo ========================================
echo.

REM 1. Detect Python
set "PYTHON_CMD=python"
where python >nul 2>&1
if %errorlevel% neq 0 (
    if exist ".venv\Scripts\python.exe" (
        echo [INFO] System python not found, trying local venv...
        set "PYTHON_CMD=.venv\Scripts\python.exe"
    ) else (
        echo [ERROR] Python not found in PATH or .venv!
        echo Please install Python 3.10+ and add to PATH.
        echo Download: https://www.python.org/downloads/
        pause
        exit /b 1
    )
)

echo Using Python: %PYTHON_CMD%
%PYTHON_CMD% --version
if %errorlevel% neq 0 (
    echo [ERROR] Selected Python command is not working.
    echo If using a venv from another computer, please delete the .venv folder and allow recreation.
    pause
    exit /b 1
)

REM 2. Check Dependencies
echo.
echo [INFO] Checking and updating dependencies...
REM Always install/upgrade requirements to ensure all packages (especially google-genai) are present
if exist "requirements.txt" (
    %PYTHON_CMD% -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to install dependencies.
        pause
        exit /b 1
    )
) else (
    echo [WARN] requirements.txt not found.
    %PYTHON_CMD% -c "import PyInstaller" 2>nul
    if %errorlevel% neq 0 (
        echo [WARN] Installing PyInstaller manually...
        %PYTHON_CMD% -m pip install pyinstaller
    )
)

REM 3. Clean Artifacts
echo.
echo [INFO] Cleaning previous build artifacts...
if exist "build" (
    rmdir /s /q "build"
    if %errorlevel% neq 0 (
        echo [ERROR] Could not delete 'build' folder. Is the app running?
        pause
        exit /b 1
    )
)
if exist "dist" (
    rmdir /s /q "dist"
    if %errorlevel% neq 0 (
        echo [ERROR] Could not delete 'dist' folder. Is the app running?
        echo Please CLOSE the MaviLojistik application and try again.
        pause
        exit /b 1
    )
)

REM 4. Build
echo.
echo [INFO] Building executable with PyInstaller...
echo.

%PYTHON_CMD% -m PyInstaller -y mavi_lojistik.spec

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Build failed!
    echo Check the error messages above.
    pause
    exit /b 1
)

REM 5. Post-Build Actions
echo.
if exist ".env" (
    echo [INFO] Copying .env to dist folder...
    copy ".env" "dist\MaviLojistik\.env" >nul
    if %errorlevel% neq 0 echo [WARN] Could not copy .env file.
)

if exist "data" (
    echo [INFO] Copying data folder to dist folder...
    xcopy /s /e /i /y "data" "dist\MaviLojistik\data" >nul
    if %errorlevel% neq 0 echo [WARN] Could not copy data folder.
)

echo.
echo ========================================
echo [SUCCESS] Build completed!
echo ========================================
echo.
echo Executable location: dist\MaviLojistik\
echo.

REM 6. Create Desktop Shortcuts
echo [INFO] Creating Desktop Shortcuts...
set "SCRIPT_PATH=%~dp0dist\MaviLojistik"
set "LOG_EXE=%SCRIPT_PATH%\MaviLojistik.exe"
set "MAH_EXE=%SCRIPT_PATH%\TanimlamaMerkezi.exe"

powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\MaviLojistik.lnk');$s.TargetPath='%LOG_EXE%';$s.WorkingDirectory='%SCRIPT_PATH%';$s.Save()"
powershell -Command "$s=(New-Object -COM WScript.Shell).CreateShortcut('%USERPROFILE%\Desktop\TanimlamaMerkezi.lnk');$s.TargetPath='%MAH_EXE%';$s.WorkingDirectory='%SCRIPT_PATH%';$s.Save()"

if %errorlevel% equ 0 (
    echo [SUCCESS] Shortcuts created on Desktop.
) else (
    echo [WARN] Could not create shortcuts automatically.
)

echo.
echo ========================================
echo [SUCCESS] Build completed successfully!
echo ========================================
pause
