@echo off
rem ============================================================
rem  تشغيل الجسر والنفق معاً بنقرة واحدة.
rem
rem  يفتح نافذتين: الأولى للجسر ينصت فيها على المنفذ المحلي،
rem  والثانية للنفق يعطي الرابط العلني الذي تطرقه تيرادينغ فيو.
rem  ويضبط ترميز النافذتين على UTF-8 كي يظهر العربي سليماً لا
rem  حروفاً مبعثرة.
rem ============================================================

chcp 65001 >nul
cd /d "%~dp0"

rem cloudflared: بجانب هذا الملف أو في المجلد الذي فوقه
set "CF=%~dp0cloudflared.exe"
if not exist "%CF%" set "CF=%~dp0..\cloudflared.exe"
if not exist "%CF%" (
    echo.
    echo [خطأ] لم يُعثر على cloudflared.exe
    echo نزّله بالأمر:
    echo   curl -L -o "%~dp0cloudflared.exe" https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-windows-amd64.exe
    echo.
    pause
    exit /b 1
)

if not exist "%~dp0.env" (
    echo.
    echo [خطأ] لا يوجد ملف .env — انسخ .env.example إليه واملأه.
    echo.
    pause
    exit /b 1
)

echo تشغيل الجسر...
start "TV Bridge" cmd /k "chcp 65001 >nul && cd /d ""%~dp0"" && python run.py"

rem مهلة تكفي ليبدأ الجسر الإنصات قبل أن يقصده النفق
timeout /t 4 /nobreak >nul

echo تشغيل النفق...
start "TV Tunnel" cmd /k "chcp 65001 >nul && ""%CF%"" tunnel --url http://127.0.0.1:8080"

echo.
echo فُتحت نافذتان:
echo   TV Bridge  ← الجسر
echo   TV Tunnel  ← النفق، وفيه الرابط العلني (trycloudflare.com)
echo.
echo انسخ الرابط من نافذة النفق وضعه في خانة Webhook URL بتيرادينغ فيو.
echo ولا تسكّر النافذتين ما دمت تريد البريدج عاملاً.
echo.
pause
