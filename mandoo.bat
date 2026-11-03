@echo off
REM ═══════════════════════════════════════════════
REM  mandoo  -  Vantage  #36693681  -  WATCH ONLY
REM    VEY GOLD VIP  -  records every signal, trades nothing
REM  Two weeks of data, then we judge the channel by numbers.
REM  Desktop shortcut: double-click to run.
REM ═══════════════════════════════════════════════
title mandoo  -  WATCH ONLY  -  VEY GOLD VIP
color 1F
cd /d "%USERPROFILE%\bot2"
echo.
echo  ===================================================
echo    mandoo   -   WATCH ONLY   -   no trading at all
echo  ---------------------------------------------------
echo    channel: VEY GOLD VIP
echo    every signal is recorded with its stop and target
echo    the price is then followed tick by tick:
echo      did it reach the level, the stop, or the target
echo      how far it dived before winning
echo      how far it ran before turning into a loss
echo  ---------------------------------------------------
echo    NOT ONE ORDER is sent to the broker
echo    open trades on this account are never touched
echo  ---------------------------------------------------
echo    data: bot2\journal\shadow.json
echo    a summary is sent to Telegram every day
echo  ===================================================
echo.
python master_bot.py ^
 --watch-only ^
 --account 36693681 --symbol XAUUSD ^
 --mt5-path "C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe" ^
 --max-loss 0 ^
 --channel "VEY GOLD VIP|lot=0.02|parser=en|sl=10|tp=10|dsl=10"
echo.
echo  [mandoo stopped]  press any key to close
pause >nul
