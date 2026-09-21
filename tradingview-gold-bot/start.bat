@echo off
rem ============================================================
rem  Start the bridge and the tunnel together, one click.
rem
rem  ASCII ONLY - do not put Arabic (or any non-ASCII) text in
rem  this file. cmd.exe parses a .bat in the console's legacy
rem  code page BEFORE `chcp 65001` can take effect, so UTF-8
rem  bytes get split into garbage tokens and every line after
rem  them fails with "is not recognized as an internal or
rem  external command". The Arabic explanation of this script
rem  lives in README.md, where it is safe.
rem ============================================================

chcp 65001 >nul
cd /d "%~dp0"

rem cloudflared: next to this file, or one folder up
set "CF=%~dp0cloudflared.exe"
if not exist "%CF%" set "CF=%~dp0..\cloudflared.exe"
if not exist "%CF%" (
    echo [ERROR] cloudflared.exe not found.
    echo Download it into this folder, then run start.bat again.
    pause
    exit /b 1
)

if not exist "%~dp0.env" (
    echo [ERROR] .env not found.
    echo Copy .env.example to .env and fill it in.
    pause
    exit /b 1
)

echo Starting bridge...
start "TV Bridge" cmd /k "chcp 65001 >nul && cd /d ""%~dp0"" && python run.py"

rem give the bridge a moment to bind its port before the tunnel dials it
timeout /t 4 /nobreak >nul

echo Starting tunnel...
start "TV Tunnel" cmd /k "chcp 65001 >nul && ""%CF%"" tunnel --url http://127.0.0.1:8080"

echo.
echo Two windows opened:
echo   TV Bridge  = the bridge
echo   TV Tunnel  = the tunnel, public URL is printed there
echo.
echo Copy that URL into the Webhook URL box in TradingView.
echo Keep both windows open while you want the bridge running.
echo.
pause
