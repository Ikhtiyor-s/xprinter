@echo off
chcp 65001 >nul 2>&1
:: BAT fayl joylashgan papkaga o'tish (muhim!)
cd /d "%~dp0"
title Nonbor Print Agent - O'rnatish
color 0A

echo.
echo ==================================================
echo    NONBOR PRINT AGENT - O'RNATISH
echo ==================================================
echo.

:: Python tekshirish
python --version >nul 2>&1
if errorlevel 1 (
    echo [XATO] Python o'rnatilmagan!
    echo.
    echo Python yuklab olish: https://www.python.org/downloads/
    echo O'rnatishda "Add to PATH" ni belgilang!
    echo.
    pause
    exit /b 1
)

echo [OK] Python topildi
python --version
echo.

:: pywin32 o'rnatish
echo [*] Kerakli kutubxonalar o'rnatilmoqda...
pip install pywin32 >nul 2>&1
if errorlevel 1 (
    echo [OGOHLANTIRISH] pywin32 o'rnatilmadi. USB printer ishlamasligi mumkin.
) else (
    echo [OK] pywin32 o'rnatildi
)

pip install requests >nul 2>&1
echo [OK] requests o'rnatildi
echo.

:: Printerlarni ko'rsatish
echo ==================================================
echo    MAVJUD PRINTERLAR
echo ==================================================
python -c "import win32print; printers = win32print.EnumPrinters(win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS); [print(f'  {i+1}. {name}') for i, (_, _, name, _) in enumerate(printers)]" 2>nul
if errorlevel 1 (
    echo   Printerlarni aniqlab bo'lmadi
)
echo.

:: config.ini sozlash
echo ==================================================
echo    SOZLAMALAR
echo ==================================================
echo.
echo config.ini faylini ochib sozlamalarni kiriting:
echo   - server url
echo   - business id
echo   - login / parol
echo   - printer nomi (yuqoridagi ro'yxatdan)
echo.

:: config.ini yo'q bo'lsa - avtomatik yaratish
if not exist "%~dp0config.ini" (
    echo [*] config.ini topilmadi - avtomatik yaratilmoqda...
    (
        echo [server]
        echo url = http://localhost:9000
        echo.
        echo [business]
        echo id = 1
        echo.
        echo [auth]
        echo username = admin
        echo password = admin123
        echo.
        echo [printer]
        echo default_printer =
        echo.
        echo [settings]
        echo poll_interval = 3
        echo paper_width = 80
    ) > "%~dp0config.ini"
    echo [OK] config.ini yaratildi
)

:: config.ini ni Notepad da ochish
echo config.ini ni ochyapman - sozlamalarni kiriting...
notepad "%~dp0config.ini"

echo.
echo ==================================================
echo    O'RNATISH TUGADI!
echo ==================================================
echo.
echo Endi start.bat ni ishga tushiring.
echo.
pause
