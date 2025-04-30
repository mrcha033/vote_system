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

@app.route('/admin/start_vote/<vote_id>')
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
def end_vote(vote_id):
    conn = get_db_connection()
    try:
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

if __name__ == '__main__':
    init_db()
    app.run(debug=True)
