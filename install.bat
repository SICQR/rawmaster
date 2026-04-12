@echo off
setlocal

echo.
echo  RAWMASTER -- Smash Daddys Audio Tools
echo  Strip it back. Own the stems.
echo.
echo Installing RAWMASTER...
echo.

where python >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Python is required. Install from https://python.org
    pause
    exit /b 1
)

python --version

echo.
echo Installing Python dependencies (this may take a few minutes)...
pip install -r requirements.txt

if %errorlevel% neq 0 (
    echo.
    echo ERROR: pip install failed. Check the error above.
    pause
    exit /b 1
)

echo.
echo Dependencies installed.
echo.
echo To run RAWMASTER:
echo   python "%~dp0rawmaster.py" track.mp3 --stems --midi
echo.
echo First run will download AI models (~110MB). One time only.
echo.

pause
