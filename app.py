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

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

# 관리자 비밀번호 설정 (환경변수에서 가져오기)
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "changeme123")

# 로그 디렉토리 생성
LOG_DIR = 'log'
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

def get_network_info():
    """현재 연결된 네트워크의 IP와 서브넷 마스크를 가져옵니다."""
    try:
        # 모든 네트워크 인터페이스 검사
        for interface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(interface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    if 'addr' in addr and 'netmask' in addr:
                        ip = addr['addr']
                        netmask = addr['netmask']
                        # localhost나 특수 IP는 제외
                        if not ip.startswith('127.') and not ip.startswith('169.254.'):
                            return ip, netmask
    except Exception as e:
        print(f"네트워크 정보 가져오기 실패: {e}")
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
    """현재 서버의 로컬 IP 주소를 가져옵니다."""
    try:
        ip, _ = get_network_info()
        if ip:
            return ip
        # fallback: 소켓을 생성하여 외부 서버에 연결 시도
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except Exception:
        return "127.0.0.1"  # 실패 시 localhost 반환

# 네트워크 정보 자동 감지
ip, netmask = get_network_info()
if ip and netmask:
    ALLOWED_NETWORK = calculate_network_range(ip, netmask)
    print(f"자동 감지된 네트워크: {ALLOWED_NETWORK}")
else:
    # 자동 감지 실패 시 환경변수나 기본값 사용
    ALLOWED_NETWORK = os.environ.get("ALLOWED_NETWORK", "192.168.1.0/24")
    print(f"네트워크 자동 감지 실패. 기본값 사용: {ALLOWED_NETWORK}")

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
    if not is_allowed_network(client_ip):
        return False, f"허용되지 않은 네트워크입니다. 회의장 내부에서 접속해주세요. (허용 네트워크: {ALLOWED_NETWORK})"
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

DB_PATH = 'data.db'

# DB 초기화
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_used BOOLEAN DEFAULT FALSE
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS vote_items (
            vote_id TEXT PRIMARY KEY,
            title TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            options TEXT,
            is_active BOOLEAN DEFAULT FALSE
        )""")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_id TEXT,
            token TEXT,
            choice TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            voter_name TEXT,
            UNIQUE(token, vote_id)
        )""")
        conn.commit()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

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
            INSERT INTO vote_items (vote_id, title, options)
            VALUES (?, ?, ?)
        ''', (vote_id, title, options))
        conn.commit()
        flash('Vote item created successfully!', 'success')
    except sqlite3.Error as e:
        flash(f'Error creating vote item: {str(e)}', 'error')
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
            SELECT voter_name, choice, timestamp 
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
        # Get all vote items with their results in a single query
        votes = conn.execute('''
            SELECT 
                vi.vote_id,
                vi.title,
                vi.options,
                vi.is_active,
                vi.created_at,
                v.choice,
                COUNT(v.choice) as vote_count
            FROM vote_items vi
            LEFT JOIN votes v ON vi.vote_id = v.vote_id
            GROUP BY vi.vote_id, v.choice
            ORDER BY vi.created_at DESC
        ''').fetchall()
        
        # Get statistics
        total_votes = conn.execute('SELECT COUNT(*) FROM votes').fetchone()[0]
        all_tokens = conn.execute('SELECT COUNT(*) FROM tokens').fetchone()[0]
        used_tokens = conn.execute('''
            SELECT COUNT(DISTINCT token_id) FROM votes
        ''').fetchone()[0]
        active_tokens = all_tokens - used_tokens

        # Process results into nested dictionary
        results = {}
        current_vote = None
        for row in votes:
            if row['vote_id'] != current_vote:
                current_vote = row['vote_id']
                results[current_vote] = {}
            if row['choice']:  # Only add if there are votes
                results[current_vote][row['choice']] = row['vote_count']

        # Get unique vote items for template
        vote_items = []
        seen_votes = set()
        active_vote_count = 0
        for row in votes:
            if row['vote_id'] not in seen_votes:
                seen_votes.add(row['vote_id'])
                vote_items.append({
                    'vote_id': row['vote_id'],
                    'title': row['title'],
                    'options': row['options'],
                    'is_active': row['is_active'],
                    'created_at': row['created_at']
                })
                if row['is_active']:
                    active_vote_count += 1

        return render_template('admin.html',
                             votes=vote_items,
                             total_votes=total_votes,
                             used_tokens=used_tokens,
                             active_tokens=active_tokens,
                             active_vote_count=active_vote_count,
                             results=results)
    finally:
        conn.close()

# 사용자: 투표 접속
@app.route('/vote')
def vote():
    token = request.args.get('token')
    if not token:
        return "토큰이 필요합니다.", 400
    
    # 네트워크 접근 권한 확인
    allowed, message = check_network_access()
    if not allowed:
        return message, 403
    
    conn = get_db_connection()
    try:
        # Check if token exists and is valid
        token_data = conn.execute('''
            SELECT id, is_used 
            FROM tokens 
            WHERE token = ?
        ''', (token,)).fetchone()
        
        if not token_data:
            return "유효하지 않은 토큰입니다.", 403
        
        if token_data['is_used']:
            return "이미 사용된 토큰입니다.", 403
        
        # Get active votes
        active_votes = conn.execute('''
            SELECT vote_id, title, options 
            FROM vote_items 
            WHERE is_active = 1
        ''').fetchall()
        
        if not active_votes:
            return "현재 진행 중인 투표가 없습니다.", 404
        
        return render_template('vote.html', 
                             token=token,
                             votes=active_votes)
    finally:
        conn.close()

def log_vote(vote_id, token, choice, voter_name):
    """투표 로그를 CSV 파일에 기록합니다."""
    log_file = os.path.join(LOG_DIR, f'votes_{datetime.now().strftime("%Y%m%d")}.csv')
    file_exists = os.path.exists(log_file)
    
    with open(log_file, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(['timestamp', 'vote_id', 'token', 'choice', 'voter_name'])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            vote_id,
            token,
            choice,
            voter_name
        ])

# 사용자: 투표 제출
@app.route('/submit_vote', methods=['POST'])
def submit_vote():
    # 네트워크 접근 권한 확인
    allowed, message = check_network_access()
    if not allowed:
        return message, 403
    
    token = request.form['token']
    vote_id = request.form['vote_id']
    choice = request.form['choice']
    voter_name = request.form.get('voter_name', '')
    
    conn = get_db_connection()
    try:
        # Get and validate token
        token_row = conn.execute('''
            SELECT id 
            FROM tokens 
            WHERE token = ? AND is_used = 0
        ''', (token,)).fetchone()
        
        if not token_row:
            return "유효하지 않거나 이미 사용된 토큰입니다.", 403
        
        token_id = token_row['id']
        
        # Insert vote and mark token as used
        conn.execute('''
            INSERT INTO votes (vote_id, token_id, choice, voter_name)
            VALUES (?, ?, ?, ?)
        ''', (vote_id, token_id, choice, voter_name))
        
        conn.execute('''
            UPDATE tokens 
            SET is_used = 1 
            WHERE id = ?
        ''', (token_id,))
        
        conn.commit()
        log_vote(vote_id, token, choice, voter_name)
        return "투표가 완료되었습니다. 감사합니다."
    except Exception as e:
        return f"투표 처리 중 오류가 발생했습니다: {str(e)}", 500
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
            SELECT DISTINCT token_id 
            FROM votes 
            WHERE vote_id = ?
        ''', (vote_id,)).fetchall()
        
        # Delete used tokens
        for token in used_tokens:
            conn.execute('''
                DELETE FROM tokens 
                WHERE id = ?
            ''', (token['token_id'],))
        
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
        conn.execute('DELETE FROM tokens WHERE is_used = 0')
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

if __name__ == '__main__':
    init_db()
    local_ip = get_local_ip()
    print(f"서버가 시작되었습니다. 로컬 IP: {local_ip}")
    print(f"허용된 네트워크: {ALLOWED_NETWORK}")
    app.run(host='0.0.0.0', port=5000, debug=True)
