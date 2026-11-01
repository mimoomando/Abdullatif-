@echo off
REM ═══════════════════════════════════════════════
REM  mandoo  -  Exness  #250950427  -  three channels
REM    VIP AN        1 x 0.05   sl 5    fixed tp 5
REM    AN Damages    1 x 0.05   sl 5    fixed tp 5
REM    VEY GOLD VIP  one per level x 0.02  sl 10  tp 10  pending
REM  Desktop shortcut: double-click to run.
REM ═══════════════════════════════════════════════
title mandoo  -  Exness 250950427  -  VIP AN + AN Damages + VEY
color 1F
cd /d "%USERPROFILE%\bot2"
echo.
echo  ===================================================
echo    mandoo   -   Exness   -   250950427      BLUE
echo  ---------------------------------------------------
echo    VIP AN         1 x 0.05   sl 5    tp 5
echo    AN Damages     1 x 0.05   sl 5    tp 5
echo    VEY GOLD VIP   1 per level x 0.02   sl 10  tp 10  pending
echo  ---------------------------------------------------
echo    SEPARATE - one channel orders never touch the other
echo  ===================================================
echo.
python master_bot.py ^
 --account 250950427 --symbol XAUUSDm ^
 --mt5-path "C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe" ^
 --max-loss 0 ^
 --channel "VIP AN|lot=0.05|pos=1|sl=5|tp=5|one" ^
 --channel "AN Damages|lot=0.05|pos=1|sl=5|tp=5|one" ^
 --channel "VEY GOLD VIP|lot=0.02|parser=en|sl=10|tp=10|dsl=10"
echo.
echo  [mandoo stopped]  press any key to close
pause >nul
