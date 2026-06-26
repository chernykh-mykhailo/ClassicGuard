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
        
        # Global spammer database (shared across all chats)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS spammer_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                chat_id INTEGER NOT NULL,
                banned_by INTEGER NOT NULL,
                reason TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS confirmed_spammers (
                user_id INTEGER PRIMARY KEY,
                reason TEXT,
                confirmed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_spammer_reports_user 
            ON spammer_reports(user_id)
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

# Spammer database functions
def report_spammer(user_id: int, chat_id: int, banned_by: int, reason: str = ""):
    """Report a user as spammer from a specific chat"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO spammer_reports (user_id, chat_id, banned_by, reason)
            VALUES (?, ?, ?, ?)
        """, (user_id, chat_id, banned_by, reason))
        conn.commit()

def check_spammer_status(user_id: int) -> dict:
    """
    Check if user is a confirmed spammer.
    Returns dict with:
      - is_confirmed: bool
      - reason: str
      - report_count: int
      - unique_chats: int
      - unique_reporters: int
    """
    with get_db() as conn:
        # Check if already confirmed
        confirmed = conn.execute(
            "SELECT * FROM confirmed_spammers WHERE user_id = ?", (user_id,)
        ).fetchone()
        
        if confirmed:
            return {
                "is_confirmed": True,
                "reason": confirmed["reason"],
                "confirmed_at": confirmed["confirmed_at"]
            }
        
        # Count reports
        reports = conn.execute(
            "SELECT * FROM spammer_reports WHERE user_id = ?", (user_id,)
        ).fetchall()
        
        report_count = len(reports)
        unique_chats = len(set(r["chat_id"] for r in reports))
        unique_reporters = len(set(r["banned_by"] for r in reports))
        
        # Smart logic to avoid false positives:
        # - NOT 3+ bans in the SAME chat from different people
        # - NOT 3+ bans from the SAME person in different chats
        # Need: at least 3 reports from different chats AND different reporters
        
        is_confirmed = (
            report_count >= 3 and
            unique_chats >= 3 and
            unique_reporters >= 3
        )
        
        return {
            "is_confirmed": is_confirmed,
            "report_count": report_count,
            "unique_chats": unique_chats,
            "unique_reporters": unique_reporters
        }

def confirm_spammer(user_id: int, reason: str = ""):
    """Mark user as confirmed spammer"""
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO confirmed_spammers (user_id, reason)
            VALUES (?, ?)
        """, (user_id, reason))
        conn.commit()
