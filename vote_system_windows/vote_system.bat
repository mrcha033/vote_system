@echo off
cd /d %~dp0
call venv-build\Scripts\activate
python launcher.py
echo.
echo 프로그램이 종료되었습니다. 종료 코드: %ERRORLEVEL%
pause
