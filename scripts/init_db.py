import sqlite3
import os
from datetime import datetime

def init_db():
    # Create database directory if it doesn't exist
    if not os.path.exists('data.db'):
        conn = sqlite3.connect('data.db')
        cursor = conn.cursor()

        # Create vote_items table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS vote_items (
            vote_id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            options TEXT NOT NULL,
            is_active BOOLEAN DEFAULT FALSE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create tokens table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS tokens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            token TEXT UNIQUE NOT NULL,
            is_used BOOLEAN DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # Create votes table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS votes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            vote_id TEXT NOT NULL,
            token INTEGER NOT NULL,
            choice TEXT NOT NULL,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (vote_id) REFERENCES vote_items (vote_id),
            FOREIGN KEY (token_id) REFERENCES tokens (id)
        )
        ''')

        # Create options table
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS options (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL
        )
        ''')

        # Insert default options
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