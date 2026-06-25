import sqlite3
import json
import os

DB_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "guard.db")

# Ensure data directory exists
os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)

def get_db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        # Settings table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                chat_id INTEGER PRIMARY KEY,
                config_json TEXT NOT NULL
            )
        """)
        # Verifications and actions log table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS verifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                chat_id INTEGER,
                user_id INTEGER,
                username TEXT,
                ip TEXT,
                user_agent TEXT,
                status TEXT, -- 'pending', 'approved', 'declined', 'banned', 'declined_but_approved', etc.
                answers TEXT, -- JSON string of answers
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def get_all_chats() -> list:
    with get_db() as conn:
        rows = conn.execute("SELECT chat_id FROM settings").fetchall()
        return [row["chat_id"] for row in rows]

def get_chat_settings(chat_id: int) -> dict:
    from src.config import DEFAULT_SETTINGS
    with get_db() as conn:
        row = conn.execute("SELECT config_json FROM settings WHERE chat_id = ?", (chat_id,)).fetchone()
        if row:
            return json.loads(row["config_json"])
        
        # Auto-register chat with default settings
        conn.execute("""
            INSERT OR IGNORE INTO settings (chat_id, config_json)
            VALUES (?, ?)
        """, (chat_id, json.dumps(DEFAULT_SETTINGS, ensure_ascii=False)))
        conn.commit()
        return DEFAULT_SETTINGS

def save_chat_settings(chat_id: int, config: dict):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO settings (chat_id, config_json)
            VALUES (?, ?)
            ON CONFLICT(chat_id) DO UPDATE SET config_json = excluded.config_json
        """, (chat_id, json.dumps(config, ensure_ascii=False)))
        conn.commit()

def log_verification_start(chat_id: int, user_id: int, username: str):
    with get_db() as conn:
        conn.execute("""
            INSERT INTO verifications (chat_id, user_id, username, status)
            VALUES (?, ?, ?, 'pending')
        """, (chat_id, user_id, username))
        conn.commit()

def log_verification_result(chat_id: int, user_id: int, ip: str, user_agent: str, status: str, answers: dict):
    with get_db() as conn:
        conn.execute("""
            UPDATE verifications
            SET ip = ?, user_agent = ?, status = ?, answers = ?
            WHERE chat_id = ? AND user_id = ? AND status = 'pending'
        """, (ip, user_agent, status, json.dumps(answers, ensure_ascii=False), chat_id, user_id))
        conn.commit()
