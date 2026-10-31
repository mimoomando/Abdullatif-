@echo off
REM ═══════════════════════════════════════════════
REM  BOT 2  -  Exness  #250950427  -  1 x 0.05
REM  شغّله بالضغط عليه مرتين. لا تكتب السطر بيدك.
REM ═══════════════════════════════════════════════
title BOT-2  Exness  250950427  -  1 x 0.05  XAUUSDm
color 1F
cd /d "%~dp0"
echo.
echo  ============================================
echo   BOT 2 - Exness - 250950427
echo   1 x 0.05  -  XAUUSDm  -  BLUE
echo   temp-sl 5   fixed-tp 5
echo  ============================================
echo.
python master_bot.py --channel "VIP AN" --account 250950427 --symbol XAUUSDm --lot 0.05 --positions 1 --one-target --temp-sl 5 --fixed-tp 5 --max-loss 0 --mt5-path "C:\Program Files\Vantage Markets MT5 Terminal\terminal64.exe"
echo.
echo  [BOT 2 stopped] press any key to close
pause >nul
