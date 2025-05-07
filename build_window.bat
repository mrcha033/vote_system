@echo off
setlocal

REM 기본 설정
set VENV_DIR=venv-build
set DIST_DIR=vote_system_windows
set ZIP_NAME=vote_system_windows.zip
set PYTHON_EXE=python

echo [1] 가상환경 생성 중...
%PYTHON_EXE% -m venv-build %VENV_DIR%

echo [2] 가상환경 활성화 및 패키지 설치...
call %VENV_DIR%\Scripts\activate
pip install --upgrade pip
pip install flask gunicorn gevent PyQt5 python-dotenv watchdog requests pillow qrcode netifaces

echo [3] 배포 폴더 구성...
mkdir %DIST_DIR%
xcopy /E /I /Y launcher.py %DIST_DIR%\
xcopy /E /I /Y server.py %DIST_DIR%\
xcopy /E /I /Y static %DIST_DIR%\static\
xcopy /E /I /Y templates %DIST_DIR%\templates\

echo [4] .env 파일 자동 생성
echo ADMIN_PASSWORD=chairperson113@ > %DIST_DIR%\.env

echo [5] 실행 스크립트 생성 중...
(
echo @echo off
echo cd /d %~dp0
echo call venv\Scripts\activate
echo python launcher.py
) > %DIST_DIR%\vote_system.bat

echo [6] 가상환경 복사 중...
xcopy /E /I /Y %VENV_DIR% %DIST_DIR%\%VENV_DIR%\

echo [7] 압축 파일 생성 중...
powershell -Command "Compress-Archive -Path '%DIST_DIR%\*' -DestinationPath '%ZIP_NAME%'"

echo [완료] %ZIP_NAME% 파일이 생성되었습니다!

endlocal
pause
