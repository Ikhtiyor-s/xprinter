@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build: NonborPrintAgent (PROD)
color 0A

echo.
echo  ============================================================
echo     PROD BUILD  ^|  NonborPrintAgent.exe
echo  ============================================================
echo.

:: IS_TEST=False ekanligini tekshir
python -c "import agent_app; assert not agent_app.IS_TEST, 'IS_TEST=True! Avval False qiling'" 2>nul
if errorlevel 1 (
    echo [XATO] agent_app.py da IS_TEST=True! False qilib qayta ishga tushiring.
    pause & exit /b 1
)

taskkill /f /im NonborPrintAgent.exe >nul 2>&1
if exist dist\NonborPrintAgent.exe del /f /q dist\NonborPrintAgent.exe >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1

echo [1/2] PROD EXE yaratilmoqda...
pyinstaller --onefile --windowed --name "NonborPrintAgent" --icon=icon.ico ^
    --hidden-import win32print --hidden-import win32api --hidden-import winreg ^
    --hidden-import pystray --hidden-import pystray._win32 ^
    --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageDraw ^
    --hidden-import requests --collect-all pystray --collect-all PIL agent_app.py

if errorlevel 1 ( echo [XATO] Build muvaffaqiyatsiz! & pause & exit /b 1 )

echo [2/2] Tayyor!
echo  dist\NonborPrintAgent.exe
echo.
pause
