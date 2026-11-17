@echo off
REM ═══════════════════════════════════════════════
REM  mandoo  -  WATCH ONLY  -  XAU Pro Operator
REM  One complete alert per signal: entry + SL + TP1/TP2/TP3.
REM  Records everything. Trades nothing. Needs no money.
REM  Works on any MT5 account: real, demo, or empty.
REM ═══════════════════════════════════════════════
title mandoo  -  WATCH ONLY  -  XAU Pro Operator
color 1F
cd /d "%USERPROFILE%\bot2"
echo.
echo  ===================================================
echo    mandoo   -   WATCH ONLY   -   no trading at all
echo  ---------------------------------------------------
echo    channel: XAU Pro Operator   (and no other)
echo  ---------------------------------------------------
echo    every message and image is archived with the
echo    gold price at that exact moment
echo  ---------------------------------------------------
echo    every signal is followed every 0.25 seconds:
echo      each time it reaches TP1, TP2, TP3
echo      each time it comes back to the entry
echo      how many points it won, how many it lost
echo    a full journey report is sent when it ends
echo  ---------------------------------------------------
echo    NOT ONE ORDER is sent to the broker
echo    open trades on this account are never touched
echo    any MT5 account works - real, demo or empty
echo    pinned to the MetaQuotes demo terminal, because five
echo    MT5 terminals are installed and python picks one blindly
echo  ---------------------------------------------------
echo    data: bot2\journal\archive  and  shadow.json
echo  ===================================================
echo.
python master_bot.py ^
 --watch-only ^
 --symbol XAUUSD ^
 --mt5-path "C:\Program Files\MetaTrader 5\terminal64.exe" ^
 --max-loss 0 ^
 --channel "XAU Pro Operator|lot=0.01|parser=xau"
echo.
echo  [mandoo stopped]  press any key to close
pause >nul
