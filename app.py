from flask import Flask, request, render_template, redirect, send_file, url_for, flash
import sqlite3
import uuid
import qrcode
import io
from zipfile import ZipFile
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
    memory_file = io.BytesIO()
    with ZipFile(memory_file, 'w') as zipf:
        for i, token in enumerate(tokens, 1):
            # Generate QR code
            qr = qrcode.QRCode(version=1, box_size=10, border=5)
            qr.add_data(token)
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
def generate_tokens():
    count = int(request.form['count'])
    tokens = []
    
    conn = get_db_connection()
    try:
        for _ in range(count):
            token = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO tokens (token)
                VALUES (?)
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
        flash(f'Error generating tokens: {str(e)}', 'error')
        return redirect(url_for('admin_dashboard'))
    finally:
        conn.close()

# 관리자: 투표 항목 생성
@app.route('/admin/create_vote', methods=['POST'])
def create_vote():
    title = request.form['title']
    vote_id = str(uuid.uuid4())
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT INTO vote_items (vote_id, title) VALUES (?, ?)", (vote_id, title))
        conn.commit()
    return redirect('/admin')

# 관리자: 현황 페이지
@app.route('/admin/status')
def vote_status():
    vote_id = request.args.get('vote_id')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT choice, COUNT(*) FROM votes WHERE vote_id = ? GROUP BY choice", (vote_id,))
        results = cur.fetchall()
    return render_template("status.html", results=results, vote_id=vote_id)

# 관리자: 대시보드
@app.route('/admin')
def admin():
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT vote_id, title FROM vote_items ORDER BY created_at DESC")
        votes = cur.fetchall()
    return render_template("admin.html", votes=votes)

# 사용자: 투표 접속
@app.route('/vote')
def vote():
    token = request.args.get('token')
    vote_id = request.args.get('vote_id')
    with sqlite3.connect(DB_PATH) as conn:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tokens WHERE token = ?", (token,))
        if not cur.fetchone():
            return "잘못된 토큰입니다.", 403
        cur.execute("SELECT * FROM vote_items WHERE vote_id = ?", (vote_id,))
        vote_info = cur.fetchone()
        if not vote_info:
            return "존재하지 않는 투표입니다.", 404
        cur.execute("SELECT * FROM votes WHERE token = ? AND vote_id = ?", (token, vote_id))
        if cur.fetchone():
            return "이미 투표하셨습니다.", 403
    return render_template("vote.html", vote_id=vote_id, token=token, title=vote_info[1])

# 사용자: 투표 제출
@app.route('/submit_vote', methods=['POST'])
def submit_vote():
    token = request.form['token']
    vote_id = request.form['vote_id']
    choice = request.form['choice']
    with sqlite3.connect(DB_PATH) as conn:
        try:
            conn.execute("INSERT INTO votes (vote_id, token, choice) VALUES (?, ?, ?)", (vote_id, token, choice))
            conn.commit()
        except sqlite3.IntegrityError:
            return "이미 투표하셨습니다.", 403
    return "투표가 완료되었습니다. 감사합니다."

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
