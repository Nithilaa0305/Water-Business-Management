@echo off
REM Build Script for Windows Executable and Packaging
echo ========================================================
echo Building Water Business Manager Windows Standalone App
echo ========================================================

set SCRIPT_DIR=%~dp0
cd /d %SCRIPT_DIR%..

echo [1/3] Activating Python Virtual Environment...
call venv\Scripts\activate.bat

echo [2/3] Running PyInstaller...
set TEMP=D:\pip_tmp
set TMP=D:\pip_tmp
pyinstaller --noconfirm --workpath D:\stock\build --distpath D:\stock\dist packaging\water_business_manager.spec

if %ERRORLEVEL% EQU 0 (
    echo [3/3] PyInstaller build completed successfully!
    echo Standalone executable is available at: dist\WaterBusinessManager\WaterBusinessManager.exe
) else (
    echo PyInstaller build encountered an error.
    exit /b %ERRORLEVEL%
)

echo Done!
pause
