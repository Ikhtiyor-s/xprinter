@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

:: 1. Django server (fon rejimda)
start "Nonbor Server" /min python manage.py runserver 0.0.0.0:8799

:: 2. ngrok tunnel (fon rejimda)
timeout /t 3 /nobreak >nul
start "ngrok Tunnel" /min ngrok http 8799 --domain=scrubbier-shantae-vaunted.ngrok-free.dev

:: 3. Agent (fon rejimda, yashirin)
timeout /t 2 /nobreak >nul
start "" /min "%~dp0agent\dist\NonborPrintAgent.exe" --minimized
