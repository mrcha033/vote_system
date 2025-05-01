import PyInstaller.__main__
import os
import shutil
import sqlite3
from datetime import datetime

def init_database():
    """데이터베이스를 초기화합니다."""
    conn = sqlite3.connect('data.db')
    cur = conn.cursor()
    
    # tokens 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tokens (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        token TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_used BOOLEAN DEFAULT FALSE
    )""")
    
    # vote_items 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS vote_items (
        vote_id TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        options TEXT,
        is_active BOOLEAN DEFAULT FALSE
    )""")
    
    # votes 테이블
    cur.execute("""
    CREATE TABLE IF NOT EXISTS votes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        vote_id TEXT,
        token_id INTEGER,
        choice TEXT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        voter_name TEXT,
        FOREIGN KEY (vote_id) REFERENCES vote_items (vote_id),
        FOREIGN KEY (token_id) REFERENCES tokens (id),
        UNIQUE(token_id, vote_id)
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
    
    # 아이콘 파일 확인
    if not os.path.exists('static/favicon.ico'):
        print("아이콘 파일이 없습니다. 먼저 create_icon.py를 실행하세요.")
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
        '--icon=static/favicon.ico',  # 아이콘 파일
        '--hidden-import=sqlite3',  # SQLite3 모듈 포함
        '--hidden-import=netifaces',  # netifaces 모듈 포함
        '--hidden-import=requests',  # requests 모듈 포함
    ]
    
    # 빌드 실행
    PyInstaller.__main__.run(options)
    
    # 빌드 후 정리
    if os.path.exists('build'):
        shutil.rmtree('build')
    if os.path.exists('vote_system.spec'):
        os.remove('vote_system.spec')
    
    print("빌드가 완료되었습니다. dist 폴더에서 vote_system.exe를 확인하세요.")
    print("주의: 실행 파일은 data.db와 log 폴더를 포함하고 있습니다.")
    print("      실행 시 자동으로 필요한 파일들이 생성됩니다.")

if __name__ == '__main__':
    build_executable() 