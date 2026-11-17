@echo off
REM ═══════════════════════════════════════════════
REM  mandoo  -  WATCH ONLY  -  two channels
REM    VEY GOLD VIP      levels follow an announced direction
REM    XAU Pro Operator  one complete alert per signal
REM  Records everything. Trades nothing. Needs no money.
REM  Works on any MT5 account: real, demo, or empty.
REM ═══════════════════════════════════════════════
title mandoo  -  WATCH ONLY  -  VEY + XAU Pro
color 1F
cd /d "%USERPROFILE%\bot2"
echo.
echo  ===================================================
echo    mandoo   -   WATCH ONLY   -   no trading at all
echo  ---------------------------------------------------
echo    VEY GOLD VIP       direction then levels
echo    XAU Pro Operator   entry + SL + TP1/TP2/TP3
echo  ---------------------------------------------------
echo    every message and image is archived with the
echo    gold price at that exact moment
echo    every signal is followed tick by tick:
echo      how many points it won, how many it lost
echo      which of their own targets it reached
echo  ---------------------------------------------------
echo    NOT ONE ORDER is sent to the broker
echo    open trades on this account are never touched
echo    any MT5 account works - real, demo or empty
echo  ---------------------------------------------------
echo    data: bot2\journal\archive  and  shadow.json
echo    a summary is sent to Telegram every day
echo  ===================================================
echo.
python master_bot.py ^
 --watch-only ^
 --symbol XAUUSD ^
 --max-loss 0 ^
 --channel "VEY GOLD VIP|lot=0.02|parser=en|sl=10|tp=30|dsl=10" ^
 --channel "XAU Pro Operator|lot=0.01|parser=xau"
echo.
echo  [mandoo stopped]  press any key to close
pause >nul
