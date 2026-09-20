@echo off
REM ============================================================
REM   XAUUSD bot - pull the latest rules, then watch the market.
REM   PAPER MODE: no orders are ever sent. Recording only.
REM   Text is kept ASCII on purpose - cmd garbles Arabic in .bat
REM   files. The Arabic reference lives in RUN.md.
REM ============================================================

cd /d "%~dp0"

echo.
echo  [1/2] Updating rules...
echo.
git pull
if errorlevel 1 (
    echo.
    echo  [!] git pull FAILED. Check the connection and run again.
    echo      The bot was NOT started.
    echo.
    pause
    exit /b 1
)

REM --- the kill switch: warn, never delete it silently ---
for %%F in (STOP STOP.txt stop stop.txt) do (
    if exist "%%F" (
        echo.
        echo  [!] A kill-switch file "%%F" is present.
        echo      The bot will RECORD but will NOT alert.
        echo      Delete that file if you did not mean to leave it.
        echo.
    )
)

echo.
echo  [2/2] Starting - stop with Ctrl+C
echo.
python -m bot.runner --watch --every 60

echo.
echo  Bot stopped. Log: runs\decisions.jsonl
echo.
pause
