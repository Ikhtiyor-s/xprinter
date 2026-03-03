@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
title Nonbor Print Agent
color 0B

echo.
echo  ____  ____  _  _  _  _  ____  ____  ____
echo (  _ \(  _ \( )( \( )(_  _)(  __)(  _ \
echo  )___/ )   / )( )  (  )(   ) _)  )   /
echo (__)  (_)\_)(___)(_)\_)(__)  (____)(_)\_)
echo.
echo       Nonbor Print Agent v2.0
echo.

:: Python tekshirish
python --version >nul 2>&1
if errorlevel 1 (
    echo [XATO] Python topilmadi!
    echo Avval setup.bat ni ishga tushiring.
    pause
    exit /b 1
)

:: config.ini tekshirish
if not exist "%~dp0config.ini" (
    echo [XATO] config.ini topilmadi!
    echo Avval setup.bat ni ishga tushiring.
    pause
    exit /b 1
)

:: Agent ishga tushirish
echo Agent ishga tushmoqda...
echo Yopish uchun Ctrl+C bosing yoki oynani yoping.
echo.

python "%~dp0print_agent.py"

echo.
echo Agent to'xtadi.
pause
