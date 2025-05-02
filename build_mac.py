import PyInstaller.__main__
import os
import shutil
import sqlite3
from datetime import datetime

def init_database():
    """데이터베이스를 초기화합니다."""
    conn = sqlite3.connect('data.db')
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_used BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS vote_items (
            vote_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            options TEXT,
            is_active BOOLEAN DEFAULT FALSE
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_id TEXT,
            token TEXT,
            choice TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(token, vote_id)
        )
    """)
    conn.commit()
    conn.close()

def create_default_env():
    """기본 환경 변수 파일을 생성합니다."""
    with open('.env', 'w') as f:
        f.write('ADMIN_PASSWORD=changeme123\n')

def build_executable():
    os.makedirs('log', exist_ok=True)
    if not os.path.exists('data.db'):
        init_database()
    if not os.path.exists('.env'):
        create_default_env()

    icon_path = os.path.abspath('static/favicon.icns')  # macOS용 .icns 아이콘 권장

    try:
        if os.path.exists('dist/vote_system'):
            os.remove('dist/vote_system')
        if os.path.exists('build'):
            shutil.rmtree('build')
        if os.path.exists('data.db'):
            os.remove('data.db')
        init_database()
        if os.path.exists('vote_system.spec'):
            os.remove('vote_system.spec')
    except Exception as e:
        print(f"이전 파일 정리 중 오류: {str(e)}")
        return

    options = [
        'launcher.py',
        '--windowed',  # GUI 앱. CLI 사용시 제거
        '--onedir',
        '--name=vote_system',
        '--add-data=static:static',
        '--add-data=templates:templates',
        '--add-data=.env:.',
        '--add-data=data.db:.',
        '--add-data=log:log',
        '--add-data=server.py:.',
        f'--icon={icon_path}' if os.path.exists(icon_path) else '',
        '--hidden-import=sqlite3',
        '--hidden-import=netifaces',
        '--hidden-import=requests',
        '--hidden-import=flask',
        '--hidden-import=jinja2',
        '--hidden-import=itsdangerous',
        '--hidden-import=click',
        '--collect-data=python-dotenv',
        '--collect-submodules=scripts',
    ]

    try:
        PyInstaller.__main__.run([opt for opt in options if opt])
        print("✅ macOS 빌드 완료: dist/vote_system")
    except Exception as e:
        print(f"❌ 빌드 실패: {str(e)}")

if __name__ == '__main__':
    build_executable()
