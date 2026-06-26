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
        
        # Chat metadata for weight calculation
        conn.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id INTEGER PRIMARY KEY,
                member_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_spammer_reports_user 
            ON spammer_reports(user_id)
        """)
        
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_spammer_reports_chat 
            ON spammer_reports(chat_id)
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
        
        # Update chat metadata
        conn.execute("""
            INSERT INTO chats (chat_id, last_updated)
            VALUES (?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET last_updated = CURRENT_TIMESTAMP
        """, (chat_id,))
        
        conn.commit()

def get_chat_weight(chat_id: int) -> float:
    """Calculate chat weight based on size and age"""
    with get_db() as conn:
        chat = conn.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
        if not chat:
            return 1.0  # Default weight
        
        weight = 1.0
        
        # Member count weight (logarithmic scale)
        member_count = chat.get("member_count", 0)
        if member_count > 100000:
            weight += 5.0
        elif member_count > 10000:
            weight += 3.0
        elif member_count > 1000:
            weight += 2.0
        elif member_count > 100:
            weight += 1.0
        
        # Age weight (older = more trusted)
        created_at = chat.get("created_at")
        if created_at:
            try:
                from datetime import datetime
                created = datetime.fromisoformat(created_at)
                age_days = (datetime.now() - created).days
                if age_days > 365:  # > 1 year
                    weight += 2.0
                elif age_days > 90:  # > 3 months
                    weight += 1.0
            except:
                pass
        
        return weight

def check_quick_bans(user_id: int, time_window_hours: int = 1) -> dict:
    """Check if user has multiple bans in short time window (rate limiting)"""
    with get_db() as conn:
        from datetime import datetime, timedelta
        cutoff = (datetime.now() - timedelta(hours=time_window_hours)).isoformat()
        
        # Count recent bans from different chats
        recent_bans = conn.execute("""
            SELECT COUNT(DISTINCT chat_id) as chat_count,
                   COUNT(*) as total_count
            FROM spammer_reports
            WHERE user_id = ? AND timestamp > ?
        """, (user_id, cutoff)).fetchone()
        
        chat_count = recent_bans["chat_count"] if recent_bans else 0
        total_count = recent_bans["total_count"] if recent_bans else 0
        
        return {
            "chat_count": chat_count,
            "total_count": total_count,
            "is_rapid": chat_count >= 3,  # 3+ different chats in 1 hour = rapid
            "time_window_hours": time_window_hours
        }

def calculate_text_similarity(text1: str, text2: str) -> float:
    """Simple text similarity using common words (0.0 to 1.0)"""
    if not text1 or not text2:
        return 0.0
    
    # Normalize texts
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    
    # Remove common stop words
    stop_words = {"і", "в", "на", "з", "до", "за", "по", "від", "про", "а", "але", "або", "що", "це", "як", "так", "вже"}
    words1 = words1 - stop_words
    words2 = words2 - stop_words
    
    if not words1 or not words2:
        return 0.0
    
    # Calculate Jaccard similarity
    intersection = len(words1 & words2)
    union = len(words1 | words2)
    
    return intersection / union if union > 0 else 0.0

def check_spammer_status(user_id: int) -> dict:
    """
    Enhanced spammer check with weights, rate limiting, and text similarity.
    Returns dict with:
      - is_confirmed: bool
      - reason: str
      - report_count: int
      - unique_chats: int
      - unique_reporters: int
      - weight: float (calculated weight score)
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
        
        # Get all reports with chat metadata
        reports = conn.execute("""
            SELECT r.*, c.member_count, c.created_at as chat_created
            FROM spammer_reports r
            LEFT JOIN chats c ON r.chat_id = c.chat_id
            WHERE r.user_id = ?
            ORDER BY r.timestamp DESC
        """, (user_id,)).fetchall()
        
        report_count = len(reports)
        unique_chats = len(set(r["chat_id"] for r in reports))
        unique_reporters = len(set(r["banned_by"] for r in reports))
        
        if report_count == 0:
            return {
                "is_confirmed": False,
                "report_count": 0,
                "unique_chats": 0,
                "unique_reporters": 0
            }
        
        # Calculate weighted score
        total_weight = 0.0
        reasons = []
        
        for report in reports:
            chat_id = report["chat_id"]
            
            # Get chat weight
            chat_weight = get_chat_weight(chat_id)
            total_weight += chat_weight
            
            # Collect reasons for similarity check
            if report["reason"]:
                reasons.append(report["reason"])
        
        # Check for rapid bans (rate limiting)
        quick_bans = check_quick_bans(user_id)
        if quick_bans["is_rapid"]:
            # Rapid bans = instant confirmation
            total_weight *= 1.5  # 50% bonus for rapid bans
        
        # Check text similarity (bonus if multiple reports have similar reasons)
        if len(reasons) >= 2:
            similar_pairs = 0
            for i in range(len(reasons)):
                for j in range(i + 1, len(reasons)):
                    similarity = calculate_text_similarity(reasons[i], reasons[j])
                    if similarity > 0.5:  # 50% similarity threshold
                        similar_pairs += 1
            
            # Bonus for similar reasons
            if similar_pairs > 0:
                similarity_bonus = min(similar_pairs * 0.5, 2.0)  # Max +2.0
                total_weight += similarity_bonus
        
        # Confirmation threshold (adjustable)
        # Default: 3.0 weight (e.g., 3 normal chats, or 1 large chat, or rapid bans)
        threshold = 3.0
        is_confirmed = total_weight >= threshold
        
        # Auto-confirm if threshold reached
        if is_confirmed:
            reason_str = f"Auto-confirmed: {report_count} reports from {unique_chats} chats by {unique_reporters} reporters"
            if quick_bans["is_rapid"]:
                reason_str += f" (RAPID: {quick_bans['chat_count']} bans in {quick_bans['time_window_hours']}h)"
            
            conn.execute("""
                INSERT INTO confirmed_spammers (user_id, reason, confirmed_at)
                VALUES (?, ?, ?)
            """, (user_id, reason_str, datetime.now().isoformat()))
            conn.commit()
        
        return {
            "is_confirmed": is_confirmed,
            "report_count": report_count,
            "unique_chats": unique_chats,
            "unique_reporters": unique_reporters,
            "weight": round(total_weight, 2),
            "threshold": threshold,
            "rapid_bans": quick_bans["is_rapid"]
        }

def confirm_spammer(user_id: int, reason: str = ""):
    """Mark user as confirmed spammer"""
    with get_db() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO confirmed_spammers (user_id, reason)
            VALUES (?, ?)
        """, (user_id, reason))
        conn.commit()

def update_chat_metadata(chat_id: int, member_count: int = 0):
    """Update chat metadata (member count, etc.)"""
    with get_db() as conn:
        conn.execute("""
            INSERT INTO chats (chat_id, member_count, last_updated)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(chat_id) DO UPDATE SET 
                member_count = excluded.member_count,
                last_updated = CURRENT_TIMESTAMP
        """, (chat_id, member_count))
        conn.commit()

def get_chat_metadata(chat_id: int) -> dict:
    """Get chat metadata"""
    with get_db() as conn:
        chat = conn.execute("SELECT * FROM chats WHERE chat_id = ?", (chat_id,)).fetchone()
        if chat:
            return dict(chat)
        return {}
