@echo off
chcp 65001 >nul
cd /d "%~dp0"
title Build: NonborPrintAgent (Flutter Windows)
color 0B

echo.
echo  ============================================================
echo     FLUTTER BUILD  ^|  NonborPrintAgent (Windows)
echo  ============================================================
echo.

set FLUTTER_PROJECT=C:\Users\Asus\nonbor_print_agent
set RELEASE_DIR=%FLUTTER_PROJECT%\build\windows\x64\runner\Release
set DIST_DIR=%~dp0dist\NonborFlutterAgent

:: Eski papkani o'chirish
if exist "%DIST_DIR%" (
    echo [1/4] Eski build tozalanmoqda...
    rmdir /s /q "%DIST_DIR%"
)

:: Flutter build
echo [2/4] Flutter Windows build boshlanmoqda...
cd /d "%FLUTTER_PROJECT%"
flutter build windows --release
if errorlevel 1 (
    echo [XATO] Flutter build muvaffaqiyatsiz!
    pause & exit /b 1
)

:: Natijani dist ga ko'chirish
echo [3/4] Natija dist papkasiga ko'chirilmoqda...
mkdir "%DIST_DIR%"
xcopy /s /e /y "%RELEASE_DIR%\*" "%DIST_DIR%\" >nul

echo [4/4] ZIP yaratilmoqda...
cd /d "%~dp0dist"
if exist "NonborFlutterAgent.zip" del /f /q "NonborFlutterAgent.zip"
powershell -Command "Compress-Archive -Path 'NonborFlutterAgent' -DestinationPath 'NonborFlutterAgent.zip'"

echo.
echo  ============================================================
echo   TAYYOR!
echo   dist\NonborFlutterAgent\nonbor_print_agent.exe
echo   dist\NonborFlutterAgent.zip
echo  ============================================================
echo.
pause
