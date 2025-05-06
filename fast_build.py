"""
build.py – PyInstaller 빌드 스크립트 (경량·고속 버전)
==================================================
- dev  : python build.py          → dist/vote_system (폴더)  ❶
- prod : python build.py --onefile → dist/vote_system.exe     ❷
"""

import argparse, os, sys, shutil, sqlite3, PyInstaller.__main__
from pathlib import Path
from datetime import datetime
from urllib.parse import quote

ROOT = Path(__file__).parent.resolve()       # 프로젝트 루트
DB   = ROOT / "data.db"
LOG  = ROOT / "log"
ENV  = ROOT / ".env"
ICON = ROOT / "static" / "favicon.ico"
ENTRY= "launcher.py"                         # 실행 진입점

# ────────────────────────────── DB / .env 초기화 ──────────────────────────────
def init_database():
    if DB.exists(): return
    with sqlite3.connect(DB) as conn:
        cur = conn.cursor()
        cur.executescript("""
            CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
            CREATE TABLE IF NOT EXISTS tokens   (
                token TEXT PRIMARY KEY,
                serial_number INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS vote_agendas (
                agenda_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS vote_items (
                vote_id TEXT PRIMARY KEY,
                agenda_id TEXT NOT NULL,
                title TEXT NOT NULL,
                options TEXT NOT NULL,
                is_active BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (agenda_id) REFERENCES vote_agendas(agenda_id)
            );
            CREATE TABLE IF NOT EXISTS votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vote_id TEXT,
                token TEXT,
                choice TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(token, vote_id)
            );
        """)
    print(f"[init] 새 데이터베이스 생성 → {DB.relative_to(ROOT)}")

def ensure_env():
    if ENV.exists(): return
    ENV.write_text("ADMIN_PASSWORD=changeme123\n", encoding="utf-8")
    print(f"[init] .env 기본 파일 생성 → {ENV.relative_to(ROOT)}")

# ────────────────────────────── PyInstaller 실행 ──────────────────────────────
def build(onefile: bool = False):
    build_dir = ROOT / "build"
    dist_dir  = ROOT / "dist"

    # 이전 결과 정리 (build 폴더/ exe 파일만)
    if build_dir.exists(): shutil.rmtree(build_dir)
    if onefile and (dist_dir / "vote_system.exe").exists():
        (dist_dir / "vote_system.exe").unlink()

    # 필수 리소스 확인
    if not ICON.exists():
        sys.exit("❌  static/favicon.ico 가 없습니다. 먼저 만들어 주세요.")

    # PyInstaller 옵션
    opts = [
        ENTRY,
        "--noconfirm",
        "--clean",
        "--log-level=WARN",
        "--console"
        "--name=vote_system",
        f"--icon={ICON}",
        f"--add-data=static{os.pathsep}static",
        f"--add-data=templates{os.pathsep}templates",
        f"--add-data=data.db{os.pathsep}.",
        f"--add-data=.env{os.pathsep}.",
        f"--add-data=log{os.pathsep}log",
        "--hidden-import=netifaces",     # 실사용 모듈만!
        "--hidden-import=qrcode",
        "--hidden-import=jinja2",
        "--hidden-import=werkzeug",
        "--hidden-import=itsdangerous",
        "--hidden-import=markupsafe",
        "--paths", str(ROOT),            # 로컬 모듈 탐색
    ]
    if onefile:
        opts.append("--onefile")
    else:
        opts.append("--onedir")

    # 빌드 실행
    print("[build] PyInstaller 시작…")
    PyInstaller.__main__.run(opts)
    kind = "exe" if onefile else "폴더"
    print(f"[build] 완료 ✔ dist/vote_system.{kind}")

# ────────────────────────────── main ──────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--onefile", action="store_true",
                        help="단일 exe(배포용) 빌드. 생략 시 onedir(개발용).")
    args = parser.parse_args()

    LOG.mkdir(exist_ok=True)
    init_database()
    ensure_env()
    build(onefile=args.onefile)
