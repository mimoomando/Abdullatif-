@echo off
REM ═══════════════════════════════════════════════
REM  mandoo  -  Exness  #250950427  -  قناتان
REM    VIP AN       1 x 0.05  وقف 5  هدف ثابت 5
REM    VEY GOLD VIP 2 x 0.02  وقف 10 هدف ثابت 10  (معلّقات)
REM  على سطح المكتب: اضغط عليه مرتين فيشتغل.
REM ═══════════════════════════════════════════════
title mandoo  -  Exness 250950427  -  VIP AN 0.05  +  VEY 0.02
color 1F
cd /d "%USERPROFILE%\bot2"
echo.
echo  ===================================================
echo    mandoo   -   Exness   -   250950427      BLUE
echo  ---------------------------------------------------
echo    VIP AN         1 x 0.05   sl 5    tp 5
echo    VEY GOLD VIP   2 x 0.02   sl 10   tp 10   pending
echo  ---------------------------------------------------
echo    القناتان منفصلتان: امر احداهما لا يمس الاخرى
echo  ===================================================
echo.
python master_bot.py ^
 --account 250950427 --symbol XAUUSDm ^
 --mt5-path "C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe" ^
 --max-loss 0 ^
 --channel "VIP AN|lot=0.05|pos=1|sl=5|tp=5|one" ^
 --channel "VEY GOLD VIP|lot=0.02|parser=en|sl=10|tp=10|dsl=10"
echo.
echo  [mandoo stopped]  press any key to close
pause >nul
