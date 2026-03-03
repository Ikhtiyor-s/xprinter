@echo off
chcp 65001 >nul 2>&1

:: ============================================================
:: Bu faylni Windows Startup papkasiga qo'ying:
::   Win+R > shell:startup > Enter
::   Bu faylni shu papkaga nusxalang
::
:: Kompyuter yoqilganda agent avtomatik ishga tushadi
:: ============================================================

cd /d "%~dp0"

python --version >nul 2>&1
if errorlevel 1 exit /b 1

if not exist "%~dp0config.ini" exit /b 1

start "Nonbor Print Agent" /min python "%~dp0print_agent.py"
