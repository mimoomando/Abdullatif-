@echo off
REM ═══════════════════════════════════════════════
REM  abdool  -  JustMarkets  #1550318365  -  two channels
REM    VIP AN       3 x 0.01 market  +  3 x 0.01 limit at coach price
REM    AN Damages   3 x 0.01 market  +  3 x 0.01 limit at coach price
REM  Desktop shortcut: double-click to run.
REM ═══════════════════════════════════════════════
title abdool  -  JustMarkets 1550318365  -  VIP AN + AN Damages  3+3 x 0.01
color 0A
cd /d "%USERPROFILE%\Desktop\mando gold\trading_bot"
echo.
echo  ===================================================
echo    abdool   -   JustMarkets   -   1550318365   GREEN
echo  ---------------------------------------------------
echo    VIP AN       3 market + 3 limit  x 0.01   sl 10 tp 10 pad 1
echo    AN Damages   3 market + 3 limit  x 0.01   sl 10 tp 10 pad 1
echo  ---------------------------------------------------
echo    3 open now at market - 3 wait as LIMIT at coach price
echo    the waiting 3 are cancelled after 15 min if price stays away
echo    daily report compares both methods in USD per trade
echo    temp sl/tp 10 points until the coach sends his own
echo    coach stop is placed 1 point further away
echo    "take from X" adds a new group at that price
echo    price chasing is OFF - no doubling in a falling market
echo    daily loss limit 200 USD - bot stops and closes all
echo  ===================================================
echo.
python master_bot.py ^
 --account 1550318365 --symbol XAUUSD.m ^
 --mt5-path "C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe" ^
 --max-loss 200 ^
 --channel "VIP AN|lot=0.01|pos=6|sl=10|ttp=10|pad=1|abe=0|chase=0|limit=3|ttl=15|one" ^
 --channel "AN Damages|lot=0.01|pos=6|sl=10|ttp=10|pad=1|abe=0|chase=0|limit=3|ttl=15|one"
echo.
echo  [abdool stopped]  press any key to close
pause >nul
