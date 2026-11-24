@echo off
setlocal
set "HERE=%~dp0"
if not exist "%HERE%frontend\dist\index.html" goto setup
if not exist "%HERE%backend\venv\Scripts\python.exe" goto setup
set "BILLING_HOST=127.0.0.1"
set "BILLING_PORT=8000"
powershell -NoProfile -Command "try { if ((Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2).app -eq 'wholesale-billing') { exit 0 } } catch {}; exit 1" >nul 2>&1
if errorlevel 1 start "Wholesale Billing Service" /min /D "%HERE%backend" "%HERE%backend\venv\Scripts\python.exe" run.py
powershell -NoProfile -Command "$deadline=(Get-Date).AddSeconds(30); while ((Get-Date) -lt $deadline) { try { if ((Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2).app -eq 'wholesale-billing') { exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; exit 1"
if errorlevel 1 goto failed
start "" "http://127.0.0.1:8000/"
exit /b 0
:setup
echo Billing has not been installed. Ask your installer to finish setup.
pause
exit /b 1
:failed
echo Billing did not start. Ask your installer to check the local database and Billing Service window.
pause
exit /b 1
