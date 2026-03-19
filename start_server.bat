@echo off
title Nonbor XPrinter Backend
echo ========================================
echo   Nonbor XPrinter Backend Server
echo   Port: 9090
echo ========================================
echo.
:loop
echo [%date% %time%] Server ishga tushmoqda...
cd /d C:\Users\Asus\xprinter
python manage.py runserver 0.0.0.0:9090
echo.
echo [%date% %time%] Server to'xtadi. 3 soniyadan qayta ishga tushadi...
timeout /t 3 /nobreak >nul
goto loop
