from flask import Flask, request, render_template, redirect, send_file, url_for, flash, session
import sqlite3
import uuid
import qrcode
import io
from zipfile import ZipFile
import os
from datetime import datetime
from functools import wraps
from dotenv import load_dotenv
import socket
import ipaddress
import netifaces
import csv
import sys
import logging

log_path = os.path.join('log', 'server_runtime.log')
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    handlers=[logging.FileHandler(log_path), logging.StreamHandler()]
)

# Load environment variables from .env file
load_dotenv(override=True)

def resource_path(relative_path):
    """PyInstaller 환경에서 리소스 경로를 정확히 가져오기 위한 함수"""
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

template_dir = resource_path("templates")
static_dir = resource_path("static")

if getattr(sys, 'frozen', False):
    base_path = sys._MEIPASS
else:
    base_path = os.path.abspath(".")

app = Flask(__name__, template_folder=template_dir, static_folder=static_dir)
app.secret_key = os.environ.get("SECRET_KEY", "fallback_secure_key")

# 관리자 비밀번호 설정 (환경변수에서 가져오기)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "chairperson113@")

# 로그 디렉토리 생성
LOG_DIR = 'log'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def is_private_ip(ip):
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False

def get_network_info():
    """기본 게이트웨이 인터페이스의 IP 및 넷마스크를 반환 (모든 인터페이스에서 시도)"""
    try:
        gws = netifaces.gateways()
        default_iface = gws.get('default', {}).get(netifaces.AF_INET, [None])[1]

        if default_iface:
            addrs = netifaces.ifaddresses(default_iface)
            inet = addrs.get(netifaces.AF_INET)
            if inet:
                for addr in inet:
                    ip = addr.get("addr")
                    netmask = addr.get("netmask")
                    if ip and netmask and ipaddress.ip_address(ip).is_private:
                        return ip, netmask

        # fallback: 모든 인터페이스 순회
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            inet = addrs.get(netifaces.AF_INET)
            if not inet:
                continue
            for addr in inet:
                ip = addr.get("addr")
                netmask = addr.get("netmask")
                if ip and netmask and ipaddress.ip_address(ip).is_private:
                    return ip, netmask
    except Exception as e:
        print(f"[!] 네트워크 정보 가져오기 실패: {e}")
    return None, None

def calculate_network_range(ip, netmask):
    """IP와 서브넷 마스크로부터 네트워크 대역을 계산합니다."""
    try:
        network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
        return str(network)
    except Exception as e:
        print(f"네트워크 대역 계산 실패: {e}")
        return None

def get_local_ip():
    """실제 유선/무선 인터페이스의 로컬 IP 주소를 가져옵니다."""
    try:
        for iface in netifaces.interfaces():
            if "VirtualBox" in iface or "VMware" in iface or "vEthernet" in iface or "Loopback" in iface:
                continue  # 가상 인터페이스 제외
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for entry in addrs[netifaces.AF_INET]:
                    ip = entry.get('addr')
                    if ip and ipaddress.ip_address(ip).is_private and not ip.startswith("192.168.56."):
                        return ip
    except:
        pass
    return "127.0.0.1"

ip, netmask = get_network_info()
if ip and netmask:
    ALLOWED_NETWORK = calculate_network_range(ip, netmask)
else:
    ALLOWED_NETWORK = "192.168.1.0/24"  # fallback
print(f"허용된 네트워크: {ALLOWED_NETWORK}")

def is_allowed_network(ip):
    """주어진 IP가 허용된 네트워크에 속하는지 확인합니다."""
    try:
        client_ip = ipaddress.ip_address(ip)
        network = ipaddress.ip_network(ALLOWED_NETWORK)
        return client_ip in network
    except ValueError:
        return False

def check_network_access():
    """네트워크 접근 권한을 확인합니다."""
    client_ip = request.remote_addr
    logging.info(f"클라이언트 IP: {client_ip} / 허용 네트워크: {ALLOWED_NETWORK}")
    print(f"접속한 클라이언트 IP: {client_ip}")
    print(f"허용된 네트워크: {ALLOWED_NETWORK}")
    if not is_allowed_network(client_ip):
        return False, f"허용되지 않은 네트워크입니다. (클라이언트 IP: {client_ip}, 허용 네트워크: {ALLOWED_NETWORK})"
    return True, None


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

if not os.path.exists('data.db'):
    from scripts.init_db import init_db
    init_db()
DB_PATH = os.path.join(os.path.dirname(__file__), 'data.db')

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
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
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
            UNIQUE(token, vote_id)
        )""")
        conn.commit()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_meeting_title():
    conn = get_db_connection()
    row = conn.execute("SELECT value FROM settings WHERE key = 'meeting_title'").fetchone()
    conn.close()
    return row["value"] if row else "회의명 미설정"

def generate_qr_zip(tokens):
    """Generate a ZIP file containing QR codes for tokens"""
    local_ip = get_local_ip()
    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zipf:
        for i, token in enumerate(tokens, 1):
            # 로컬 IP 기반 URL 생성
            voting_url = f"http://{local_ip}:5000/vote?token={token}"
            
            # Generate QR code with the full URL
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(voting_url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Save QR code to memory
            img_byte_arr = io.BytesIO()
            img.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            # Add to ZIP
            zipf.writestr(f'token_{i:03d}.png', img_byte_arr)
    
    memory_file.seek(0)
    return memory_file

@app.route('/')
def index():
    return '서버가 실행중입니다', 200

@app.route('/admin/generate_tokens', methods=['POST'])
@login_required
def generate_tokens():
    count = int(request.form['count'])
    if count <= 0:
        flash('생성할 토큰 수는 1 이상이어야 합니다.', 'error')
        return redirect(url_for('admin_dashboard'))
    
    tokens = []
    conn = get_db_connection()
    try:
        for _ in range(count):
            token = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO tokens (token, created_at)
                VALUES (?, datetime('now'))
            ''', (token,))
            tokens.append(token)
        conn.commit()
        
        # Generate and return ZIP file
        zip_file = generate_qr_zip(tokens)
        return send_file(
            zip_file,
            mimetype='application/zip',
            as_attachment=True,
            download_name=f'voting_tokens_{datetime.now().strftime("%Y%m%d_%H%M%S")}.zip'
        )
    except sqlite3.Error as e:
        flash(f'토큰 생성 중 오류가 발생했습니다: {str(e)}', 'error')
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

    conn = get_db_connection()
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
    
    conn = get_db_connection()
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
    conn = get_db_connection()
    try:
        # 전체 안건 목록
        agenda_rows = conn.execute('SELECT * FROM vote_agendas ORDER BY created_at DESC').fetchall()
        
        # 모든 표결 항목
        vote_rows = conn.execute('SELECT * FROM vote_items ORDER BY created_at DESC').fetchall()

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
    conn = get_db_connection()
    conn.execute('INSERT INTO vote_agendas (agenda_id, title) VALUES (?, ?)', (agenda_id, title))
    conn.commit()
    conn.close()
    flash("안건이 등록되었습니다.")
    return redirect(url_for('admin_dashboard'))


# 사용자: 투표 접속
@app.route('/vote')
def vote():
    allowed, message = check_network_access()
    if not allowed:
        return message, 403
    token = request.args.get("token")
    if not token:
        return "토큰이 누락되었습니다.", 400

    conn = get_db_connection()
    try:
        # 토큰 유효성 검증
        token_row = conn.execute("SELECT * FROM tokens WHERE token = ?", (token,)).fetchone()
        if not token_row:
            return render_template("vote.html", grouped_votes=[], token=token, error="유효하지 않은 토큰입니다.")

        # 활성 vote_items + 연결된 안건 불러오기
        vote_rows = conn.execute('''
            SELECT va.agenda_id, va.title as agenda_title,
                   vi.vote_id, vi.title as subtitle, vi.options
            FROM vote_items vi
            JOIN vote_agendas va ON vi.agenda_id = va.agenda_id
            WHERE vi.is_active = 1
            ORDER BY va.created_at DESC, vi.created_at ASC
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

        return render_template("vote.html", meeting_title=get_meeting_title(), token=token, grouped_votes=list(grouped.values()))
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
    # 네트워크 접근 권한 확인
    allowed, message = check_network_access()
    if not allowed:
        return message, 403
    
    token = request.form.get('token')
    if not token:
        return "토큰이 누락되었습니다.", 400

    conn = get_db_connection()
    try:
        # 1. 토큰 유효성 확인
        token_row = conn.execute(
            "SELECT token FROM tokens WHERE token = ?", (token,)
        ).fetchone()
        if not token_row:
            flash("유효하지 않거나 만료된 토큰입니다.", "error")
            return redirect(url_for("vote", token=token))

        # 2. 모든 choice_* 항목을 순회하며 투표 삽입
        for key in request.form:
            if key.startswith("choice_"):
                vote_id = key.split("_", 1)[1]
                choice = request.form.get(key)

                # 중복 투표 확인
                already_voted = conn.execute(
                    "SELECT 1 FROM votes WHERE vote_id = ? AND token = ?",
                    (vote_id, token)
                ).fetchone()
                if already_voted:
                    flash(f"이미 투표한 항목이 있습니다. (vote_id={vote_id})", "error")
                    continue

                # 투표 삽입
                conn.execute(
                    "INSERT INTO votes (vote_id, token, choice) VALUES (?, ?, ?)",
                    (vote_id, token, choice)
                )
                log_vote(vote_id, token, choice)

        conn.commit()
        flash("모든 투표가 성공적으로 제출되었습니다.", "success")
        return redirect(url_for("vote", token=token))

    except Exception as e:
        return f"투표 처리 중 오류 발생: {str(e)}", 500
    finally:
        conn.close()
@app.route('/admin/start_vote/<vote_id>')
@login_required
def start_vote(vote_id):
    conn = get_db_connection()
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
    conn = get_db_connection()
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
    conn = get_db_connection()
    try:
        # Get all tokens used in this vote
        used_tokens = conn.execute('''
            SELECT DISTINCT token 
            FROM votes 
            WHERE vote_id = ?
        ''', (vote_id,)).fetchall()
        
        # Delete used tokens
        for token in used_tokens:
            conn.execute('''
                DELETE FROM tokens 
                WHERE id = ?
            ''', (token['token'],))
        
        # Delete the vote item
        conn.execute('''
            DELETE FROM vote_items 
            WHERE vote_id = ?
        ''', (vote_id,))
        
        conn.commit()
        flash('Vote and related tokens cleaned up successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error cleaning up vote: {str(e)}', 'error')
    finally:
        conn.close()
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_tokens', methods=['POST'])
@login_required
def delete_tokens():
    conn = get_db_connection()
    try:
        # 사용되지 않은 모든 토큰 삭제
        conn.execute('DELETE FROM tokens WHERE token = ?')
        conn.commit()
        flash('미사용 의결권이 모두 삭제되었습니다.', 'success')
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