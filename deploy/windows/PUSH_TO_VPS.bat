@echo off
title Chronicles of Ven - Push to VPS
color 0B

echo.
echo  ================================================
echo   Chronicles of Ven -- Push Changes to VPS
echo  ================================================
echo.
echo  This will copy code changes to the server and
echo  restart both services. Takes about 30 seconds.
echo.
pause

cd /d "%~dp0..\.."

echo.
echo  [1/3] Copying code to VPS...
scp -r src api ui scripts config.yaml requirements.txt root@216.250.112.169:/opt/inherited-cloud/
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: File transfer failed. Check your SSH connection.
    pause
    exit /b 1
)

echo.
echo  [2/3] Restarting API service...
ssh root@216.250.112.169 "systemctl restart novel-api"
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Could not restart novel-api.
    pause
    exit /b 1
)

echo.
echo  [3/3] Restarting UI service...
ssh root@216.250.112.169 "systemctl restart novel-ui"
if %errorlevel% neq 0 (
    echo.
    echo  ERROR: Could not restart novel-ui.
    pause
    exit /b 1
)

echo.
echo  ================================================
echo   Done! Changes are live at:
echo   https://novel.talos-advisory.com
echo  ================================================
echo.
pause
