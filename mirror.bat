@echo off
chcp 65001 >nul
title mirror - READ ONLY - JustMarkets
cd /d "%~dp0"

REM Read-only mirror of another account. Never trades.
REM Log in to that account in MT5 yourself (investor password
REM is enough). No password is stored here.
REM Change the account number and the MT5 path below.

python mirror.py ^
 --account 0000000 ^
 --mt5-path "C:\Program Files\JustMarkets MetaTrader 5\terminal64.exe" ^
 --symbol XAUUSD.m

pause
