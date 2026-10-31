@echo off
REM ═══════════════════════════════════════════════
REM  abdool  -  JustMarkets  #1550318365  -  4 x 0.01
REM  على سطح المكتب: اضغط عليه مرتين فيشتغل.
REM ═══════════════════════════════════════════════
title abdool  -  JustMarkets 1550318365  -  4 x 0.01  XAUUSD.m
color 0A
cd /d "%USERPROFILE%\Desktop\mando gold\trading_bot"
echo.
echo  ===============================================
echo    abdool   -   JustMarkets   -   1550318365
echo    4 x 0.01      XAUUSD.m      GREEN
echo  ===============================================
echo.
python master_bot.py --channel "VIP AN" --symbol XAUUSD.m --account 1550318365 --one-target --mt5-path "C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe"
echo.
echo  [abdool stopped]  press any key to close
pause >nul
