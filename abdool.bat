@echo off
REM ═══════════════════════════════════════════════
REM  abdool  -  JustMarkets  #1550318365  -  two channels
REM    VIP AN       4 x 0.01   limit entry at coach price
REM    AN Damages   4 x 0.01   limit entry at coach price
REM  Desktop shortcut: double-click to run.
REM ═══════════════════════════════════════════════
title abdool  -  JustMarkets 1550318365  -  VIP AN + AN Damages  4 x 0.01
color 0A
cd /d "%USERPROFILE%\Desktop\mando gold\trading_bot"
echo.
echo  ===================================================
echo    abdool   -   JustMarkets   -   1550318365   GREEN
echo  ---------------------------------------------------
echo    VIP AN         4 x 0.01   sl 10  tp 10  pad 1
echo    AN Damages     4 x 0.01   sl 10  tp 10  pad 1
echo  ---------------------------------------------------
echo    entry is a LIMIT order at the coach's own price
echo    no entry at a worse price - cancelled after 15 min
echo    temp sl/tp 10 points until the coach sends his own
echo    coach stop is placed 1 point further away
echo    "take from X" adds a new group of 4 at that price
echo    price chasing is OFF - no doubling in a falling market
echo    daily loss limit 200 USD - bot stops and closes all
echo  ===================================================
echo.
python master_bot.py ^
 --account 1550318365 --symbol XAUUSD.m ^
 --mt5-path "C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe" ^
 --max-loss 200 ^
 --channel "VIP AN|lot=0.01|pos=4|sl=10|ttp=10|pad=1|abe=0|chase=0|limit=1|ttl=15|one" ^
 --channel "AN Damages|lot=0.01|pos=4|sl=10|ttp=10|pad=1|abe=0|chase=0|limit=1|ttl=15|one"
echo.
echo  [abdool stopped]  press any key to close
pause >nul
