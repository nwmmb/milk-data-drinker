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

".venv\Scripts\python.exe" -c "import milk_data_drinker, requests" >nul 2>nul
if errorlevel 1 (
    echo Installing downloader dependencies inside .venv...
    ".venv\Scripts\python.exe" -m pip install -e ".[download]"
    if errorlevel 1 goto :setup_error
)

".venv\Scripts\python.exe" -m milk_data_drinker.downloader %*
exit /b %errorlevel%

:setup_error
echo.
echo Setup failed. Confirm that Python 3.10 or newer is installed, then try again.
pause
exit /b 1
