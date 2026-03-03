@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Nonbor Print Agent - Build
color 0A

echo.
echo  ============================================================
echo     NONBOR PRINT AGENT  ^|  EXE YARATISH
echo  ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 ( echo [XATO] Python topilmadi! & pause & exit /b 1 )
python --version

echo.
echo [1/4] Kutubxonalar o'rnatilmoqda...
pip install pyinstaller pywin32 pystray Pillow requests --quiet
echo  [OK]
echo.

echo [2/4] Eski build tozalanmoqda...
if exist dist\NonborPrintAgent.exe del /f /q dist\NonborPrintAgent.exe >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1
if exist NonborPrintAgent.spec del /f /q NonborPrintAgent.spec >nul 2>&1

echo.
echo [3/4] EXE yaratilmoqda (2-4 daqiqa)...
echo.

pyinstaller ^
    --onefile ^
    --windowed ^
    --name "NonborPrintAgent" ^
    --hidden-import win32print ^
    --hidden-import win32api ^
    --hidden-import winreg ^
    --hidden-import pystray ^
    --hidden-import pystray._win32 ^
    --hidden-import PIL ^
    --hidden-import PIL.Image ^
    --hidden-import PIL.ImageDraw ^
    --hidden-import requests ^
    --collect-all pystray ^
    --collect-all PIL ^
    agent_app.py

if errorlevel 1 ( echo. & echo [XATO] Build muvaffaqiyatsiz! & pause & exit /b 1 )

echo.
echo [4/4] Tarqatish papkasi...
if exist config.ini copy /y config.ini dist\config.ini >nul
echo  [OK] dist\NonborPrintAgent.exe

echo.
echo  ============================================================
echo     TAYYOR!  dist\NonborPrintAgent.exe
echo  ============================================================
echo.
echo  Mijozga faqat EXE fayl yuboring.
echo  Birinchi ishga tushganda config.ini avtomatik yaratiladi.
echo.
pause
