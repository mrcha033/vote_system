import PyInstaller.__main__
import os
import shutil
import sqlite3
from datetime import datetime

def init_database():
    """데이터베이스를 초기화합니다."""
    conn = sqlite3.connect('data.db')
    cur = conn.cursor()

    # settings 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )""")
    
    # tokens 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_used BOOLEAN DEFAULT FALSE
    )""")
    
    #안건 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vote_agendas (
            agenda_id TEXT PRIMARY KEY,
            title TEXT NOT NULL, --이게 "안건명"
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
    
    #표결 테이블
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vote_items (
            vote_id TEXT PRIMARY KEY,
            agenda_id TEXT NOT NULL,
            title TEXT NOT NULL, -- 이게 "표결명"
            options TEXT NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (agenda_id) REFERENCES vote_agendas(agenda_id)
        )""")
    
    # votes 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vote_id TEXT,
        token TEXT UNIQUE,
        choice TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        voter_name TEXT,
        FOREIGN KEY (vote_id) REFERENCES vote_items (vote_id),
        FOREIGN KEY (token) REFERENCES tokens(token),
        UNIQUE(token, vote_id)
    )""")
    
    conn.commit()
    conn.close()

def create_default_env():
    """기본 환경 변수 파일을 생성합니다."""
    with open('.env', 'w') as f:
        f.write('ADMIN_PASSWORD=changeme123\n')

def build_executable():
    # 필요한 디렉토리 생성
    os.makedirs('log', exist_ok=True)
    
    # 데이터베이스 초기화
    if not os.path.exists('data.db'):
        init_database()
    
    # 기본 환경 변수 파일 생성
    if not os.path.exists('.env'):
        create_default_env()
    
    # 아이콘 파일 확인 및 절대 경로 설정
    icon_path = os.path.abspath('static/favicon.ico')
    if not os.path.exists(icon_path):
        print("아이콘 파일이 없습니다. 먼저 create_icon.py를 실행하세요.")
        return
    
    # 이전 빌드 파일 정리
    try:
        # 이전 실행 파일 삭제
        exe_path = os.path.join('dist', 'vote_system.exe')
        if os.path.exists(exe_path):
            os.remove(exe_path)
            
        # 이전 빌드 디렉토리 삭제
        if os.path.exists('build'):
            shutil.rmtree('build')

        if os.path.exists('data.db'):
            os.remove('data.db')
        init_database()

        # 이전 spec 파일 삭제
        if os.path.exists('vote_system.spec'):
            os.remove('vote_system.spec')
            
    except Exception as e:
        print(f"이전 빌드 파일 정리 중 오류 발생: {str(e)}")
        print("실행 중인 vote_system.exe를 종료하고 다시 시도하세요.")
        return
    
    # 빌드 옵션 설정
    options = [
        'launcher.py',  # 메인 스크립트
        '--noconsole',  # 콘솔 창 숨기기
        '--onefile',    # 단일 실행 파일 생성
        '--name=vote_system',  # 실행 파일 이름
        '--add-data=static;static',  # 정적 파일 포함
        '--add-data=templates;templates',  # 템플릿 파일 포함
        '--add-data=.env;.',  # 환경 변수 파일 포함
        '--add-data=data.db;.',  # 데이터베이스 파일 포함
        '--add-data=log;log',  # 로그 디렉토리 포함
        '--add-data=server.py;.',  # server.py 파일 포함
        f'--icon={icon_path}' if os.path.exists(icon_path) else '',  # 아이콘 파일 (절대 경로 사용)
        '--hidden-import=sqlite3',  # SQLite3 모듈 포함
        '--hidden-import=netifaces',  # netifaces 모듈 포함
        '--hidden-import=requests',  # requests 모듈 포함
        '--hidden-import=flask',  # Flask 모듈 포함
        '--hidden-import=flask_sqlalchemy',  # Flask-SQLAlchemy 모듈 포함
        '--hidden-import=flask_login',  # Flask-Login 모듈 포함
        '--hidden-import=werkzeug.security',  # Werkzeug security 모듈 포함
        '--hidden-import=jinja2',  # Jinja2 템플릿 엔진 포함
        '--hidden-import=markupsafe',  # MarkupSafe 포함
        '--hidden-import=itsdangerous',  # itsdangerous 포함
        '--hidden-import=click',  # Click 포함
        '--hidden-import=PyQt5',  # PyQt5 포함
        '--hidden-import=PyQt5.QtCore',  # PyQt5.QtCore 포함
        '--hidden-import=PyQt5.QtGui',  # PyQt5.QtGui 포함
        '--hidden-import=PyQt5.QtWidgets',  # PyQt5.QtWidgets 포함
        '--exclude-module=pkg_resources',  # pkg_resources 제외
        '--exclude-module=jaraco',  # jaraco 제외
        '--exclude-module=backports',  # backports 제외
        '--runtime-hook=runtime_hook.py',  # 런타임 훅 추가
        '--collect-data=python-dotenv',  # python-dotenv 데이터 포함
        '--collect-submodules=scripts',
    ]
    
    try:
        # 빌드 실행
        PyInstaller.__main__.run([opt for opt in options if opt])
        
        print("빌드가 완료되었습니다. dist 폴더에서 vote_system.exe를 확인하세요.")
        print("주의: 실행 파일은 data.db와 log 폴더를 포함하고 있습니다.")
        print("      실행 시 자동으로 필요한 파일들이 생성됩니다.")
        
    except Exception as e:
        print(f"빌드 중 오류 발생: {str(e)}")
        print("실행 중인 vote_system.exe를 종료하고 다시 시도하세요.")

if __name__ == '__main__':
    build_executable() 