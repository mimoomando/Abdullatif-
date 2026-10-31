@echo off
REM ═══════════════════════════════════════════════
REM  BOT 1  -  JustMarkets  #1550318365  -  4 x 0.01
REM  شغّله بالضغط عليه مرتين. لا تكتب السطر بيدك.
REM ═══════════════════════════════════════════════
title BOT-1  JustMarkets  1550318365  -  4 x 0.01  XAUUSD.m
color 0A
cd /d "%~dp0"
echo.
echo  ============================================
echo   BOT 1 - JustMarkets - 1550318365
echo   4 x 0.01  -  XAUUSD.m  -  GREEN
echo  ============================================
echo.
python master_bot.py --channel "VIP AN" --symbol XAUUSD.m --account 1550318365 --one-target --mt5-path "C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe"
echo.
echo  [BOT 1 stopped] press any key to close
pause >nul
