@echo off
REM ═══════════════════════════════════════════════
REM  abdool  -  JustMarkets  #1550318365  -  two channels
REM    VIP AN       4 x 0.01   sl 5   one target
REM    AN Damages   4 x 0.01   sl 5   one target
REM  Desktop shortcut: double-click to run.
REM ═══════════════════════════════════════════════
title abdool  -  JustMarkets 1550318365  -  VIP AN + AN Damages  4 x 0.01
color 0A
cd /d "%USERPROFILE%\Desktop\mando gold\trading_bot"
echo.
echo  ===================================================
echo    abdool   -   JustMarkets   -   1550318365   GREEN
echo  ---------------------------------------------------
echo    VIP AN         4 x 0.01   sl 5   one target
echo    AN Damages     4 x 0.01   sl 5   one target
echo  ---------------------------------------------------
echo    SEPARATE - one channel orders never touch the other
echo  ===================================================
echo.
python master_bot.py ^
 --account 1550318365 --symbol XAUUSD.m ^
 --mt5-path "C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe" ^
 --channel "VIP AN|lot=0.01|pos=4|sl=5|one" ^
 --channel "AN Damages|lot=0.01|pos=4|sl=5|one"
echo.
echo  [abdool stopped]  press any key to close
pause >nul
