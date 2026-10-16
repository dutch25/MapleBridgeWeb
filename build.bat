@echo off
setlocal
cd /d "%~dp0"

echo =======================================================
echo    KUROMS WEB CLIENT - EXE BUILDER (PyInstaller)
echo =======================================================

echo.
echo [1/3] Kiem tra thu vien phu thuoc...
py -m pip install --upgrade pip
py -m pip install requests pysher websocket-client pyinstaller keyboard opencv-python numpy mss

echo.
echo [2/3] Tien hanh dong goi MapleDiscordBridge_Web.exe...
echo.

py -m PyInstaller ^
    --onefile ^
    --console ^
    --uac-admin ^
    --add-data "templates;templates" ^
    --name MapleDiscordBridge_Web ^
    MapleDiscordBridge_WebClient.py

echo.
echo [3/3] Sao chep config va templates vao thu muc dist...
if not exist "dist" mkdir dist
if exist "config.ini" copy /Y "config.ini" "dist\config.ini"
if exist "Mo_KuroMS.bat" copy /Y "Mo_KuroMS.bat" "dist\Mo_KuroMS.bat"
if exist "templates" (
    if not exist "dist\templates" mkdir "dist\templates"
    copy /Y "templates\*.png" "dist\templates\"
)

echo.
echo =======================================================
echo                 DONG GOI THANH CONG!
echo =======================================================
echo.
echo File thuc thi:
echo %~dp0dist\MapleDiscordBridge_Web.exe
echo.
pause
