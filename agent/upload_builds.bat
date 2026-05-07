@echo off
chcp 65001 >nul
title Nonbor - Build yuklash

set SERVER=https://printer.nonbor.uz/api/v2
set /p TOKEN=Admin token kiriting:

echo.
echo [1/3] NonborPrintAgent.exe yuklanmoqda...
curl -s -X POST "%SERVER%/downloads/upload/" ^
  -H "Authorization: Token %TOKEN%" ^
  -F "file=@dist\NonborPrintAgent.exe" ^
  -F "filename=NonborPrintAgent.exe"

echo.
echo [2/3] NonborFlutterAgent.zip yuklanmoqda...
if exist "dist\NonborFlutterAgent.zip" (
    curl -s -X POST "%SERVER%/downloads/upload/" ^
      -H "Authorization: Token %TOKEN%" ^
      -F "file=@dist\NonborFlutterAgent.zip" ^
      -F "filename=NonborFlutterAgent.zip"
) else (
    echo [skip] NonborFlutterAgent.zip topilmadi - avval build_flutter.bat ishga tushiring
)

echo.
echo [3/3] NonborPrinter.apk yuklanmoqda...
curl -s -X POST "%SERVER%/downloads/upload/" ^
  -H "Authorization: Token %TOKEN%" ^
  -F "file=@..\mobile\build\app\outputs\flutter-apk\app-release.apk" ^
  -F "filename=NonborPrinter.apk"

echo.
echo Tayyor!
pause
