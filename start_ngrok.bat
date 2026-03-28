@echo off
chcp 65001 >nul 2>&1
title Nonbor Print Server - ngrok Tunnel

echo.
echo  ========================================
echo   Nonbor Print Server - Internet Tunnel
echo   Domain: scrubbier-shantae-vaunted.ngrok-free.dev
echo  ========================================
echo.
echo Boshqa kompyuterlardan ulash uchun:
echo   https://scrubbier-shantae-vaunted.ngrok-free.dev
echo.
echo Yopish uchun Ctrl+C bosing.
echo.

ngrok http 8799 --domain=scrubbier-shantae-vaunted.ngrok-free.dev
