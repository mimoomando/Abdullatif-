@echo off
chcp 65001 >nul
title mandoo - DEMO 0.05 - XAU Pro Operator
cd /d "%~dp0"

REM Demo account only. --account pins it to 115910230 so it
REM cannot run anywhere else. --demo allows a demo account.
REM No password here: MT5 is already logged in, the bot attaches.

python master_bot.py ^
 --demo ^
 --symbol XAUUSD ^
 --mt5-path "C:\Program Files\MetaTrader 5\terminal64.exe" ^
 --account 115910230 ^
 --no-manual ^
 --max-loss 0 ^
 --channel "XAU Pro Operator|lot=0.05|pos=1|parser=xau|trade|nostop=10|abe=0"

pause
