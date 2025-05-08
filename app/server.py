from flask import Flask, request, render_template, redirect, send_file, url_for, flash, session, Response, abort
import sqlite3
import uuid
import qrcode
import io
from zipfile import ZipFile, ZIP_DEFLATED
import os
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import csv
import sys
import logging
from PIL import ImageDraw, ImageFont
from urllib.parse import quote 
from pathlib import Path

# ── ① 실행 디렉터리 결정 ─────────────────────────
load_dotenv(override=True)

APP_DIR  = os.path.dirname(__file__)
DB_PATH  = os.path.join(APP_DIR, "data.db")
LOG_DIR  = os.path.join(APP_DIR, "log")
os.makedirs(LOG_DIR, exist_ok=True)

# ── ② 로그 폴더/파일 준비 ────────────────────────
LOG_DIR  = APP_DIR / "log"
LOG_DIR.mkdir(exist_ok=True)                        # 폴더가 없으면 생성
LOG_FILE = LOG_DIR / "server_runtime.log"

# ── ③ 로깅 설정 ───────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)]
)
logging.info("Logger ready → %s", LOG_FILE)

BASE_URL        = os.getenv("BASE_URL")           # ex) https://vote-system.fly.dev
SECRET_KEY      = os.getenv("SECRET_KEY", "change_me")
ADMIN_PASSWORD  = os.getenv("ADMIN_PASSWORD", "chairperson113@")

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = SECRET_KEY

def public_base_url():
    if BASE_URL:
        return BASE_URL.rstrip("/")
    # 프록시 헤더를 믿고 프로토콜 계산
    proto = request.headers.get("X-Forwarded-Proto", "http")
    return f"{proto}://{request.host}"


# 로그인 상태 체크 함수
def is_logged_in():
    return session.get('logged_in') is True

# 로그인 필요 데코레이터
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_logged_in():
            flash('관리자 로그인이 필요합니다.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 로그인 라우트
@app.route('/login', methods=['GET', 'POST'])
def login():
    if is_logged_in():
        return redirect(url_for('admin_dashboard'))
        
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['logged_in'] = True
            flash('로그인 성공', 'success')
            return redirect(url_for('admin_dashboard'))
        else:
            flash('비밀번호가 올바르지 않습니다.', 'error')
    return render_template('login.html')

# 로그아웃 라우트
@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    flash('로그아웃 되었습니다.', 'success')
    return redirect(url_for('login'))

# DB 초기화
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
        """)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            serial_number INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vote_agendas (
            agenda_id TEXT PRIMARY KEY,
            title TEXT NOT NULL, --이게 "안건명"
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )""")
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
        cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_id TEXT,
            token TEXT,
            choice TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            voter_name TEXT,
            UNIQUE(token, vote_id),          -- ✔ 복합 제약만
            FOREIGN KEY (vote_id) REFERENCES vote_items(vote_id),
            FOREIGN KEY (token)   REFERENCES tokens(token)
        )
        """)
        conn.commit()

if not os.path.exists(DB_PATH):
    init_db()           # ← 이걸 호출


def db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def get_meeting_title():
    conn = db()
    row = conn.execute("SELECT value FROM settings WHERE key = 'meeting_title'").fetchone()
    conn.close()
    return row["value"] if row else "회의명 미설정"

def generate_qr_zip(tokens):
    print("QR ZIP 생성 시작")
    memory_file = io.BytesIO()

    with ZipFile(memory_file, 'w') as zipf:
        for token, serial in tokens:
            print(f"QR 생성 중: {serial=}")
            voting_url = f"{public_base_url()}/vote?token={token}"
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(voting_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

            try:
                draw = ImageDraw.Draw(img)
                text = f"{serial:03d}"
                bbox = draw.textbbox((0, 0), text)
                text_width = bbox[2] - bbox[0]
                text_height = bbox[3] - bbox[1]
                img_width, img_height = img.size
                draw.text(
                    ((img_width - text_width) / 2, img_height - text_height - 10),
                    text, fill="black"
                )
            except Exception as draw_err:
                print(f"텍스트 추가 실패: {draw_err}")

            try:
                img_byte_arr = io.BytesIO()
                img.save(img_byte_arr, format='PNG')
                img_byte_arr.seek(0)
                zipf.writestr(f'token_{serial:03d}.png', img_byte_arr.read())
            except Exception as zip_err:
                print(f"ZIP에 쓰기 실패: {zip_err}")

    memory_file.seek(0)
    print("QR ZIP 생성 완료")
    return memory_file

@app.route('/')
def index():
    return '서버가 실행중입니다', 200

@app.route('/admin/generate_tokens', methods=['POST'])
@login_required
def generate_tokens():
    print("토큰 생성중")
    try:
        count = int(request.form['count'])
        if count <= 0:
            flash('생성할 토큰 수는 1 이상이어야 합니다.', 'error')
            return redirect(url_for('admin_dashboard'))
    except (KeyError, ValueError):
        flash('수량이 잘못되었습니다.', 'error')
        return redirect(url_for('admin_dashboard'))

    tokens = []
    conn = db()
    try:
        # ① 토큰·시리얼 DB 저장
        cur = conn.execute("SELECT COALESCE(MAX(serial_number), 0) FROM tokens")
        current_max = cur.fetchone()[0]

        for i in range(count):
            serial = current_max + i + 1
            token  = str(uuid.uuid4())
            conn.execute(
                "INSERT INTO tokens (token, serial_number, created_at) "
                "VALUES (?, ?, datetime('now'))",
                (token, serial)
            )
            tokens.append((token, serial))
        conn.commit()

        # ② QR → ZIP 메모리 생성
        zip_bytes = generate_qr_zip(tokens)
        zip_bytes.seek(0)                       # **반드시 한 번만!**

        # ③ 파일 전송
        filename          = f"voting_tokens_{datetime.now():%Y%m%d_%H%M%S}.zip"
        encoded_filename  = quote(filename)

        # Flask ≥2.0 : download_name 만 주면 Content-Disposition 자동 완성
        response = send_file(
            zip_bytes,
            mimetype="application/zip",
            as_attachment=True,
            download_name=filename
        )

        # (Flask 1.x 호환용) 직접 헤더를 건드리고 싶다면 ↓ 처럼 덮어쓰기
        response.headers["Content-Disposition"] = (
            f"attachment; filename*=UTF-8''{encoded_filename}"
        )
        return response

    except Exception as e:
        conn.rollback()
        flash(f"토큰 생성 중 오류 발생: {e}", "error")
        logging.exception("token generation failed")
        return redirect(url_for('admin_dashboard'))
    finally:
        conn.close()

# 관리자: 투표 항목 생성
@app.route('/admin/create_vote', methods=['POST'])
@login_required
def create_vote():
    agenda_id = request.form['agenda_id']
    title = request.form['title']
    options = request.form['options']
    vote_id = str(uuid.uuid4())

    # Validate options
    if not options.strip():
        flash('Options cannot be empty.', 'error')
        return redirect(url_for('admin_dashboard'))

    conn = db()
    try:
        conn.execute('''
            INSERT INTO vote_items (vote_id, agenda_id, title, options)
            VALUES (?, ?, ?, ?)
        ''', (vote_id, agenda_id, title, options))
        conn.commit()
        flash('표결이 등록되었습니다!', 'success')
    except sqlite3.Error as e:
        flash(f'표결 등록 중 오류 발생생: {str(e)}', 'error')
    finally:
        conn.close()

    return redirect(url_for('admin_dashboard'))

# 관리자: 현황 페이지
@app.route('/admin/status')
def vote_status():
    vote_id = request.args.get('vote_id')
    if not vote_id:
        flash('Vote ID is required', 'error')
        return redirect(url_for('admin_dashboard'))
    
    conn = db()
    try:
        # Get vote details
        vote = conn.execute('''
            SELECT * FROM vote_items 
            WHERE vote_id = ?
        ''', (vote_id,)).fetchone()
        
        if not vote:
            flash('Vote not found', 'error')
            return redirect(url_for('admin_dashboard'))
        
        # Get vote results
        results = conn.execute('''
            SELECT choice, COUNT(*) as count 
            FROM votes 
            WHERE vote_id = ? 
            GROUP BY choice
        ''', (vote_id,)).fetchall()
        
        # Get recent votes
        recent_votes = conn.execute('''
            SELECT choice, timestamp 
            FROM votes 
            WHERE vote_id = ? 
            ORDER BY timestamp DESC 
            LIMIT 10
        ''', (vote_id,)).fetchall()
        
        total_votes = sum(row['count'] for row in results)
        
        return render_template('status.html',
                             vote=vote,
                             results={row['choice']: row['count'] for row in results},
                             recent_votes=recent_votes,
                             total_votes=total_votes)
    finally:
        conn.close()

# 관리자: 대시보드
@app.route('/admin')
@login_required
def admin_dashboard():
    conn = db()
    try:
        # 전체 안건 목록
        agenda_rows = conn.execute('SELECT * FROM vote_agendas ORDER BY created_at ASC').fetchall()
        
        # 모든 표결 항목
        vote_rows = conn.execute('SELECT * FROM vote_items ORDER BY agenda_id ASC, created_at ASC').fetchall()

        # 안건에 따라 표결 항목 묶기
        agenda_dict = {}
        for agenda in agenda_rows:
            agenda_dict[agenda['agenda_id']] = {
                'agenda_id': agenda['agenda_id'],
                'title': agenda['title'],
                'items': []
            }

        for vote in vote_rows:
            vote_item = {
                'vote_id': vote['vote_id'],
                'title': vote['title'],
                'options': vote['options'],
                'is_active': vote['is_active']
            }
            if vote['agenda_id'] in agenda_dict:
                agenda_dict[vote['agenda_id']]['items'].append(vote_item)

        agendas = list(agenda_dict.values())

        # 통계
        total_agendas = len(agendas)
        total_votes = len(vote_rows)
        active_votes = sum(1 for v in vote_rows if v['is_active'])

        used_tokens = conn.execute('SELECT COUNT(DISTINCT token) FROM votes').fetchone()[0]
        all_tokens = conn.execute('SELECT COUNT(*) FROM tokens').fetchone()[0]
        active_tokens = all_tokens - used_tokens

        return render_template('admin.html',
                               meeting_title=get_meeting_title(),
                               agendas=agendas,
                               total_agendas=total_agendas,
                               total_votes=total_votes,
                               active_votes=active_votes,
                               used_tokens=used_tokens,
                               active_tokens=active_tokens)
    finally:
        conn.close()


@app.route('/admin/create_agenda', methods=['POST'])
@login_required
def create_agenda():
    title = request.form['agenda_title']
    agenda_id = str(uuid.uuid4())
    conn = db()
    conn.execute('INSERT INTO vote_agendas (agenda_id, title) VALUES (?, ?)', (agenda_id, title))
    conn.commit()
    conn.close()
    flash("안건이 등록되었습니다.")
    return redirect(url_for('admin_dashboard'))


# 사용자: 투표 접속
@app.route('/vote')
def vote():
    token = request.args.get("token")
    if not token:
        return "토큰이 누락되었습니다.", 400

    conn = db()
    try:
        # 토큰 유효성 검증
        token_row = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        if not token_row:
            return render_template("vote.html", grouped_votes=[], token=token, error="유효하지 않은 토큰입니다.")
        serial_number = token_row['serial_number']
        # 활성 vote_items + 연결된 안건 불러오기
        vote_rows = conn.execute('''
            SELECT va.agenda_id, va.title as agenda_title,
                   vi.vote_id, vi.title as subtitle, vi.options
            FROM vote_items vi
            JOIN vote_agendas va ON vi.agenda_id = va.agenda_id
            WHERE vi.is_active = 1
            ORDER BY va.created_at ASC, vi.created_at ASC
        ''').fetchall()

        # grouped_votes 형태로 변환
        grouped = {}
        for row in vote_rows:
            aid = row['agenda_id']
            if aid not in grouped:
                grouped[aid] = {
                    'agenda_id': aid,
                    'title': row['agenda_title'],
                    'items': []
                }
            grouped[aid]['items'].append({
                'vote_id': row['vote_id'],
                'subtitle': row['subtitle'],
                'options': row['options']
            })

        return render_template("vote.html", meeting_title=get_meeting_title(), token=token, serial_number=serial_number, grouped_votes=list(grouped.values()))
    finally:
        conn.close()

def log_vote(vote_id, token, choice):
    """투표 로그를 CSV 파일에 기록합니다."""
    log_file = os.path.join(LOG_DIR, f'votes_{datetime.now().strftime("%Y%m%d")}.csv')
    file_exists = os.path.exists(log_file)
    
    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['timestamp', 'vote_id', 'token', 'choice'])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            vote_id,
            token,
            choice
        ])

# 사용자: 투표 제출
@app.route('/submit_vote', methods=['POST'])
def submit_vote():
    token = request.form.get('token')
    if not token:
        return "토큰이 누락되었습니다.", 400

    conn = db()
    try:
        token_row = conn.execute(
            "SELECT token FROM tokens WHERE token = ?", (token,)
        ).fetchone()
        if not token_row:
            flash("유효하지 않거나 만료된 토큰입니다.", "error")
            return redirect(url_for("vote", token=token))

        # 기존 투표 내역 미리 조회
        voted_rows = conn.execute(
            "SELECT vote_id FROM votes WHERE token = ?", (token,)
        ).fetchall()
        already_voted_ids = set(row["vote_id"] for row in voted_rows)

        success_count = 0
        duplicate_count = 0
        insert_queue = []

        for key in request.form:
            if key.startswith("choice_"):
                vote_id = key.split("_", 1)[1]
                choice = request.form.get(key)
                if not choice:
                    continue

                if vote_id in already_voted_ids:
                    duplicate_count += 1
                    continue

                insert_queue.append((vote_id, token, choice))

        try:
            for vote_id, token, choice in insert_queue:
                conn.execute(
                    "INSERT INTO votes (vote_id, token, choice) VALUES (?, ?, ?)",
                    (vote_id, token, choice)
                )
                log_vote(vote_id, token, choice)
                success_count += 1
            conn.commit()
        except sqlite3.IntegrityError as e:
            conn.rollback()
            logging.error(f"투표 삽입 실패: {str(e)}")
            flash("투표 중 오류가 발생하여 일부 항목이 저장되지 않았습니다.", "error")
            return redirect(url_for("vote", token=token))


        # 메시지 출력
        if success_count > 0:
            conn.commit()
            flash(f"{success_count}개 항목에 투표가 성공적으로 제출되었습니다.", "success")

        if duplicate_count > 0:
            flash(f"{duplicate_count}개 항목은 이미 투표하여 제외되었습니다.", "info")

        if success_count == 0 and duplicate_count == 0:
            flash("선택된 항목이 없습니다.", "warning")


        return redirect(url_for("vote", token=token))

    except Exception as e:
        conn.rollback()
        return f"투표 처리 중 오류 발생: {str(e)}", 500
    finally:
        conn.close()

@app.route('/admin/start_vote/<vote_id>')
@login_required
def start_vote(vote_id):
    conn = db()
    try:
        conn.execute('''
            UPDATE vote_items 
            SET is_active = 1 
            WHERE vote_id = ?
        ''', (vote_id,))
        conn.commit()
        flash('Vote started successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error starting vote: {str(e)}', 'error')
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/end_vote/<vote_id>')
@login_required
def end_vote(vote_id):
    conn = db()
    try:
        # End the vote
        conn.execute('''
            UPDATE vote_items 
            SET is_active = 0 
            WHERE vote_id = ?
        ''', (vote_id,))
        conn.commit()
        flash('Vote ended successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error ending vote: {str(e)}', 'error')
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/cleanup_vote/<vote_id>')
@login_required
def cleanup_vote(vote_id):
    conn = db()
    try:
        # Get all tokens used in this vote
        conn.execute(
            'DELETE FROM votes WHERE vote_id = ?',
            (vote_id,)
        )

        # ② 표결 자체 제거
        conn.execute(
            'DELETE FROM vote_items WHERE vote_id = ?',
            (vote_id,)
        )

        conn.commit()
        flash('표결이 삭제되었습니다.', 'success')

    except sqlite3.Error as e:
        conn.rollback()
        flash(f'표결 삭제 중 오류: {e}', 'error')

    finally:
        conn.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_agenda/<agenda_id>')
@login_required
def delete_agenda(agenda_id):
    conn = db()
    try:
        # ① 먼저 이 안건에 속한 vote_id 목록을 구함
        vote_id_rows = conn.execute(
            'SELECT vote_id FROM vote_items WHERE agenda_id = ?',
            (agenda_id,)
        ).fetchall()
        vote_ids = [row['vote_id'] for row in vote_id_rows]

        # ② vote_id 들에 남아 있는 투표 기록 삭제
        if vote_ids:
            conn.executemany(
                'DELETE FROM votes WHERE vote_id = ?',
                [(vid,) for vid in vote_ids]
            )

        # ③ vote_items 삭제
        conn.execute(
            'DELETE FROM vote_items WHERE agenda_id = ?',
            (agenda_id,)
        )

        # ④ 마지막으로 안건 자체 삭제
        conn.execute(
            'DELETE FROM vote_agendas WHERE agenda_id = ?',
            (agenda_id,)
        )

        conn.commit()
        flash('안건과 관련 표결이 모두 삭제되었습니다.', 'success')

    except sqlite3.Error as e:
        conn.rollback()
        flash(f'안건 삭제 중 오류: {e}', 'error')

    finally:
        conn.close()

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_tokens', methods=['POST'])
@login_required
def delete_tokens():
    conn = db()
    try:
        # 모든 토큰 삭제
        conn.execute('DELETE FROM tokens')
        conn.commit()
        flash('모든 의결권이 삭제되었습니다.', 'success')
    except Exception as e:
        conn.rollback()
        flash('의결권 삭제 중 오류가 발생했습니다.', 'error')
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/export_logs', methods=['GET'])
@login_required
def export_logs():
    """로그 파일을 ZIP으로 압축하여 다운로드합니다."""
    try:
        memory_file = io.BytesIO()
        with ZipFile(memory_file, 'w') as zipf:
            for filename in os.listdir(LOG_DIR):
                if filename.endswith('.csv'):
                    file_path = os.path.join(LOG_DIR, filename)
                    zipf.write(file_path, filename)
        
        memory_file.seek(0)
        return send_file(
            memory_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'vote_logs_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
    except Exception as e:
        flash(f'로그 내보내기 실패: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))

@app.route('/shutdown', methods=['POST'])
def shutdown():
    if not request.environ.get('werkzeug.server.shutdown'):
        return 'Not running with the Werkzeug Server', 500
    request.environ['werkzeug.server.shutdown']()
    return 'Server shutting down...', 200