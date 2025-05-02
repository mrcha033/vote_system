import sqlite3
import os
from datetime import datetime

def init_db():
    if not os.path.exists('data.db'):
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()

        # vote_items 테이블 생성
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vote_items (
            vote_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            options TEXT NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # tokens 테이블 생성 (is_used 제거)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            token TEXT PRIMARY KEY,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # votes 테이블 생성 (token은 문자열, 중복 투표 방지 위해 UNIQUE)
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_id TEXT NOT NULL,
            token TEXT NOT NULL,
            choice TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vote_id) REFERENCES vote_items (vote_id),
            FOREIGN KEY (token) REFERENCES tokens (token),
            UNIQUE(token, vote_id)
        )
        ''')

        # (선택) 옵션 목록 관리용 테이블
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        ''')
        default_options = ['Option 1', 'Option 2', 'Option 3']
        cursor.executemany('INSERT OR IGNORE INTO options (name) VALUES (?)',
                           [(option,) for option in default_options])

        conn.commit()
        conn.close()
        print("Database initialized successfully!")
    else:
        print("Database already exists.")

if __name__ == '__main__':
    init_db()
