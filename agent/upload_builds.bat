@echo off
chcp 65001 >nul
title Nonbor - Build yuklash

set SERVER=https://printer.nonbor.uz/api/v2
set /p TOKEN=Admin token kiriting:

echo.
echo [1/2] NonborPrintAgent.exe yuklanmoqda...
curl -s -X POST "%SERVER%/downloads/upload/" ^
  -H "Authorization: Token %TOKEN%" ^
  -F "file=@dist\NonborPrintAgent.exe" ^
  -F "filename=NonborPrintAgent.exe"

echo.
echo [2/2] NonborPrinter.apk yuklanmoqda...
curl -s -X POST "%SERVER%/downloads/upload/" ^
  -H "Authorization: Token %TOKEN%" ^
  -F "file=@..\mobile\build\app\outputs\flutter-apk\app-release.apk" ^
  -F "filename=NonborPrinter.apk"

echo.
echo Tayyor!
pause
