@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Creating a private Python environment in .venv...
    where py >nul 2>nul
    if errorlevel 1 (
        python -m venv .venv
    ) else (
        py -3 -m venv .venv
    )
    if errorlevel 1 goto :setup_error
)

if exist ".venv\.mdd-packaged-v2" goto :old_environment
if not exist ".venv\.timeless-downloader-v1" goto :install
".venv\Scripts\python.exe" -I -c "import timeless_downloader, requests, tkcalendar" >nul 2>nul
if errorlevel 1 goto :install
goto :launch

:install
echo Installing downloader dependencies inside .venv...
".venv\Scripts\python.exe" -m pip install ".[download]"
if errorlevel 1 goto :setup_error
type nul > ".venv\.timeless-downloader-v1"

:launch
".venv\Scripts\python.exe" -I -m timeless_downloader %*
exit /b %errorlevel%

:old_environment
echo.
echo This is a renamed downloader-only release.
echo Delete the .venv folder, then run this launcher again.
pause
exit /b 1

:setup_error
echo.
echo Setup failed. Confirm that Python 3.10 or newer is installed, then try again.
pause
exit /b 1
