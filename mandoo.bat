@echo off
chcp 65001 >nul
title mandoo - DEMO 0.05 - XAU Pro Operator
cd /d "%~dp0"

REM حسابٌ تجريبي فقط. --account يمنع التشغيل على غيره،
REM و--demo يسمح بالتجريبي صراحةً. لا كلمة مرور هنا:
REM البوت يلتحق بالمنصّة المفتوحة وهي مسجّلةٌ دخولها.

python master_bot.py ^
 --demo ^
 --symbol XAUUSD ^
 --mt5-path "C:\Program Files\MetaTrader 5\terminal64.exe" ^
 --account 115873892 ^
 --no-manual ^
 --max-loss 0 ^
 --channel "XAU Pro Operator|lot=0.05|pos=1|parser=xau|trade|nostop=10"

pause
