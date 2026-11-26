@echo off
chcp 65001 >nul
title mirror - READ ONLY - 1550400047
cd /d "%~dp0"

REM Read-only mirror of someone else's account. It never trades:
REM the order function itself is replaced by a refusal before any
REM connection is made.
REM
REM Log in to 1550400047 inside the JustMarkets MT5 yourself.
REM The INVESTOR (read-only) password is enough and is safer.
REM No password is stored in this file.
REM
REM Watches every symbol on the account, not just gold.

python mirror.py ^
 --account 1550400047 ^
 --mt5-path "C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe"

pause
