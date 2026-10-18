@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
set "PYTHONUTF8=1"
if exist "%~dp0.venv\Scripts\python.exe" (
  "%~dp0.venv\Scripts\python.exe" launcher.py
  goto finished
)
if exist "%LocalAppData%\Programs\Python\Python311\python.exe" (
  "%LocalAppData%\Programs\Python\Python311\python.exe" launcher.py
  goto finished
)
where py >nul 2>nul
if not errorlevel 1 (
  py -3 launcher.py
  goto finished
)
where python >nul 2>nul
if not errorlevel 1 (
  python launcher.py
  goto finished
)
echo Python was not found. Please install Python 3.10 or newer.
:finished
echo.
echo The application has stopped. Startup details are saved in the work folder.
pause
endlocal
