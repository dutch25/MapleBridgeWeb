@echo off
title KuroMS Web Launcher

echo =======================================================
echo    KHOI DONG KUROMS WEB (HO TRO AUTO DANH NGAM)
echo =======================================================
echo.

set "EDGE_EXE=C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE_EXE%" set "EDGE_EXE=C:\Program Files\Microsoft\Edge\Application\msedge.exe"

set "CHROME_EXE=C:\Program Files\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"

set FLAGS=--app=https://play.playkuro.com/ --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="%LOCALAPPDATA%\KuroMS_Browser" --disable-background-timer-throttling --disable-backgrounding-occluded-windows --disable-renderer-backgrounding --enable-gpu-rasterization --enable-zero-copy --ignore-gpu-blocklist --use-angle=d3d11 --force-device-scale-factor=1 --disable-features=WakeLock

powercfg -requestsoverride PROCESS msedge.exe awaymode display system >nul 2>&1
powercfg -requestsoverride PROCESS chrome.exe awaymode display system >nul 2>&1

if exist "%EDGE_EXE%" (
    echo [OK] Dang mo KuroMS tren Microsoft Edge...
    start "" "%EDGE_EXE%" %FLAGS%
    goto done
)

if exist "%CHROME_EXE%" (
    echo [OK] Dang mo KuroMS tren Google Chrome...
    start "" "%CHROME_EXE%" %FLAGS%
    goto done
)

start https://play.playkuro.com/

:done
echo.
echo [THANH CONG] Da khoi dong xong! Cua so game da mo.
echo Cua so nay se tu dong dong sau 3 giay...
timeout /t 3 >nul 2>&1
