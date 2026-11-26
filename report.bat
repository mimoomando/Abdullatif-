@echo off
chcp 65001 >nul
title mirror report
cd /d "%~dp0"

REM Reads what was recorded and prints the analysis.
REM Does not connect to MT5. Safe to run any time.

python mirror.py --report

pause
