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

if not exist ".venv\.mdd-packaged-v2" goto :install
".venv\Scripts\python.exe" -I -c "import milk_data_drinker, requests, tkcalendar" >nul 2>nul
if errorlevel 1 goto :install
goto :launch

:install
echo Installing downloader dependencies inside .venv...
".venv\Scripts\python.exe" -m pip install ".[download]"
if errorlevel 1 goto :setup_error
type nul > ".venv\.mdd-packaged-v2"

:launch
".venv\Scripts\python.exe" -I -m milk_data_drinker.downloader %*
exit /b %errorlevel%

:setup_error
echo.
echo Setup failed. Confirm that Python 3.10 or newer is installed, then try again.
pause
exit /b 1
