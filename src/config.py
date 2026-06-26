import os
from dotenv import load_dotenv

# Load env variables from root level
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://yourdomain.com")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

DEFAULT_SETTINGS = {
    # Core behavior
    "action": "decline",  # 'decline', 'ban', or 'approve_log'
    "guard_mode": True,
    
    # Essential checks (enabled by default)
    "check_ip": True,           # Block same IP
    "check_avatar": True,       # Require avatar
    "avatar_min_count": 1,
    "check_fingerprint": True,  # Canvas/WebGL fingerprint
    "check_account_age": True,  # Block young accounts
    "min_account_age_months": 3,
    "check_cas": True,          # CAS anti-spam (free, fast)
    "cas_action": "block",
    
    # Optional checks (disabled by default)
    "check_device": False,
    "check_premium": False,
    "check_language": False,
    "log_languages": [],
    "check_osint": False,       # Requires userbot setup
    "osint_action": "log",
    
    # Questions
    "questions_count": 1,
    "log_channel": "",    # ID of the channel for logs
    "contact_link": "",
    "decline_msg_captcha": "",  # Message when captcha failed
    "decline_msg_twink": "",   # Message when suspected twink (IP/avatar)
    "questions": [
        {"type": "emoji", "q": "Де паляниця? 🧐", "correct": "🫓", "distractors": ["🍓", "🍓", "🍓", "🍓", "🍓", "🍓", "🍓", "🍓"]},
        {"type": "text", "q": "Чий Крим?", "a": ["український", "україна", "україни"], "choices": ["Україна", "Росія", "Нічий", "Спірний"]},
        {"type": "text", "q": "Батько наш - ...?", "a": ["бандера"], "choices": ["Бандера", "Шевченко", "Франко", "Мазепа"]},
        {"type": "text", "q": "Україна - це ...?", "a": ["європа", "понад усе"]},
        {"type": "text", "q": "Столиця України?", "a": ["київ", "kyiv"], "choices": ["Київ", "Москва", "Мінськ", "Варшава"]},
        {"type": "text", "q": "Якою мовою розмовляють в Україні?", "a": ["українською", "українська"]},
        {"type": "emoji", "q": "Яка тварина символ України? 🐺", "correct": "🐺", "distractors": ["🦊", "🐻", "🐗", "🦌", "🦅", "🐱", "🐶", "🐰"]},
        {"type": "text", "q": "Якого кольору прапор України?", "a": ["синьо-жовтий", "синій і жовтий", "blue and yellow", "жовто-блакитний"], "choices": ["Синьо-жовтий", "Червоно-чорний", "Біло-червоний", "Зелено-жовтий"]},
    ]
}