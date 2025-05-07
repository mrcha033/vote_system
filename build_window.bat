@echo off
chcp 65001 >nul
setlocal

REM ────────────────────────────────────────────────
REM 1. 초기 설정
set VENV_DIR=venv-build
set DIST_DIR=vote_system_windows
set ZIP_NAME=vote_system_windows.zip
set PYTHON_EXE=python

REM ────────────────────────────────────────────────
echo [1] 가상환경 생성 중...
%PYTHON_EXE% -m venv %VENV_DIR%

REM ────────────────────────────────────────────────
echo [2] 패키지 설치 중...
call %VENV_DIR%\Scripts\activate
pip install --upgrade pip
pip install flask waitress python-dotenv PyQt5 watchdog requests pillow qrcode netifaces

REM ────────────────────────────────────────────────
echo [3] 배포 디렉토리 구성 중...
mkdir %DIST_DIR%

copy /Y launcher.py %DIST_DIR%\
copy /Y server.py   %DIST_DIR%\
xcopy /E /I /Y static %DIST_DIR%\static\
xcopy /E /I /Y templates %DIST_DIR%\templates\

REM ────────────────────────────────────────────────
echo [4] .env 파일 생성 중...
echo ADMIN_PASSWORD=chairperson113@ > %DIST_DIR%\.env
echo STATIC_SERVER_IP=165.132.176.34 >> %DIST_DIR%\.env

REM ────────────────────────────────────────────────
echo [5] 실행 배치파일 생성 중...
(
echo @echo off
chcp 65001 >nul
echo cd /d %%~dp0
echo call %VENV_DIR%\Scripts\activate
echo python launcher.py
echo echo.
echo echo 프로그램이 종료되었습니다. 종료 코드: %%ERRORLEVEL%%
echo pause
) > %DIST_DIR%\vote_system.bat

REM ────────────────────────────────────────────────
echo [6] 가상환경 복사 중...
xcopy /E /I /Y %VENV_DIR% %DIST_DIR%\%VENV_DIR%\

REM ────────────────────────────────────────────────
echo [7] ZIP 압축 중...
del %ZIP_NAME% >nul 2>&1
powershell -Command "Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath '%ZIP_NAME%' -Force"

echo [✅ 완료] 배포 ZIP 파일 생성: %ZIP_NAME%
endlocal
pause
