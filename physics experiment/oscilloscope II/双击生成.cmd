@echo off
chcp 65001 >nul
setlocal
python "%~dp0个性化生成.py" %*
set "run_result=%errorlevel%"
echo.
pause
exit /b %run_result%
