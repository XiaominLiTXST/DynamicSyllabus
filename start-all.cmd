@echo off
cd /d "%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\manage.ps1" start
echo.
echo Waiting for the services to start...
timeout /t 8 /nobreak >nul
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\scripts\manage.ps1" status
pause
