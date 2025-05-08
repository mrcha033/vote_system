"""
app/server.py – Fly.io 전용 버전
* 0.0.0.0:$PORT 에서 실행
* BASE_URL 환경변수(또는 request.host_url)로 QR 만들기
* 네트워크 ACL → 선택적(환경변수 ALLOWED_NETWORK 없으면 스킵)
* SQLite WAL + 볼륨(/data)에 저장
"""
import os, io, uuid, csv, logging, sqlite3
from datetime import datetime
from urllib.parse import quote

from flask import Flask, request, render_template, redirect, url_for, flash, send_file, session, abort
import qrcode
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import ImageDraw, ImageFont

# ── 기본 설정 ───────────────────────────────────────────
DB_PATH = "/data/data.db"                     # Fly 볼륨에 저장
os.makedirs("/data", exist_ok=True)

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.environ.get("SECRET_KEY", "CHANGE_ME")
BASE_URL      = os.environ.get("BASE_URL")    # ex) https://vote-system.fly.dev
ADMIN_PASSWORD= os.environ.get("ADMIN_PASSWORD", "chairperson113@")
ALLOWED_NET   = os.environ.get("ALLOWED_NETWORK")  # 값이 있으면 IP ACL 활성화

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)s  %(message)s")

# ── 선택적 IP ACL ──────────────────────────────────────
import ipaddress
@app.before_request
def ip_acl():
    if not ALLOWED_NET:
        return                      # ACL 비활성
    if request.remote_addr not in ipaddress.ip_network(ALLOWED_NET):
        abort(403)

# ── DB 초기화 (WAL 모드) ────────────────────────────────
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript("""
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS tokens (
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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
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
init_db()

def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

# ── 유틸 ────────────────────────────────────────────────
def public_base_url():
    """Fly 로 배포되면 BASE_URL 또는 X-Forwarded-Proto 헤더 기반으로 도메인 계산."""
    if BASE_URL:
        return BASE_URL.rstrip("/")
    proto = request.headers.get("X-Forwarded-Proto", "http")
    return f"{proto}://{request.host}"

def generate_qr_zip(pairs):
    """[(token, serial)] → 메모리 ZIP(PNG)"""
    bio = io.BytesIO()
    with ZipFile(bio, "w", ZIP_DEFLATED) as z:
        for tok, sn in pairs:
            url = f"{public_base_url()}/vote?token={tok}"
            qr  = qrcode.make(url).convert("RGB")
            canvas = ImageDraw.Draw(qr)
            canvas.text((10, qr.size[1]-30), f"{sn:03}", fill="black")
            buf = io.BytesIO(); qr.save(buf, format="PNG"); buf.seek(0)
            z.writestr(f"token_{sn:03}.png", buf.read())
    bio.seek(0)
    return bio

# ── 라우팅 (필요 부분만) ────────────────────────────────
def logged_in(): return session.get("logged_in")
def login_required(f):
    from functools import wraps
    @wraps(f)
    def _(*a, **kw):
        if not logged_in(): return redirect(url_for("login"))
        return f(*a, **kw)
    return _

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method=="POST":
        if request.form["password"]==ADMIN_PASSWORD:
            session["logged_in"]=True; return redirect("/admin")
        flash("Wrong password"); return redirect("/login")
    return render_template("login.html")

@app.route("/admin/generate_tokens", methods=["POST"])
@login_required
def generate_tokens():
    count = int(request.form["count"])
    with db() as conn:
        cur = conn.execute("SELECT COALESCE(MAX(serial_number),0) FROM tokens")
        base = cur.fetchone()[0]
        pairs=[]
        for i in range(count):
            serial = base+i+1
            tok = str(uuid.uuid4())
            conn.execute("INSERT INTO tokens(token,serial_number) VALUES(?,?)",(tok,serial))
            pairs.append((tok,serial))
        conn.commit()
    return send_file(generate_qr_zip(pairs),
                     mimetype="application/zip",
                     as_attachment=True,
                     download_name=f"tokens_{datetime.utcnow():%Y%m%d_%H%M%S}.zip")

# …(기존 vote / submit_vote / admin 대시보드 등 그대로 유지)…

@app.route("/")
def health(): return "OK", 200

# ── 엔트리포인트 ───────────────────────────────────────
if __name__ == "__main__":
    # Fly는 gunicorn으로 실행되지만, 로컬 디버그용
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
