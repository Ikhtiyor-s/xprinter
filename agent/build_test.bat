@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build: NonborPrintAgent TEST
color 0E

echo.
echo  ============================================================
echo     TEST BUILD  ^|  NonborPrintAgent-Test.exe
echo  ============================================================
echo.

:: Vaqtincha IS_TEST=True qilib nusxa olamiz
python -c "
content = open('agent_app.py', encoding='utf-8').read()
content = content.replace('IS_TEST = False', 'IS_TEST = True', 1)
open('_agent_test.py', 'w', encoding='utf-8').write(content)
print('OK')
"
if errorlevel 1 ( echo [XATO] & pause & exit /b 1 )

taskkill /f /im NonborPrintAgent-Test.exe >nul 2>&1
if exist dist\NonborPrintAgent-Test.exe del /f /q dist\NonborPrintAgent-Test.exe >nul 2>&1
if exist build rmdir /s /q build >nul 2>&1

echo [1/2] TEST EXE yaratilmoqda...
pyinstaller --onefile --windowed --name "NonborPrintAgent-Test" --icon=icon.ico ^
    --hidden-import win32print --hidden-import win32api --hidden-import winreg ^
    --hidden-import pystray --hidden-import pystray._win32 ^
    --hidden-import PIL --hidden-import PIL.Image --hidden-import PIL.ImageDraw ^
    --hidden-import requests --collect-all pystray --collect-all PIL _agent_test.py

if errorlevel 1 (
    del /f /q _agent_test.py >nul 2>&1
    echo [XATO] Build muvaffaqiyatsiz! & pause & exit /b 1
)

del /f /q _agent_test.py >nul 2>&1

echo [2/2] Tayyor!
echo  dist\NonborPrintAgent-Test.exe
echo.
pause
