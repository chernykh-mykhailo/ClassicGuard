import os
from dotenv import load_dotenv

# Load env variables from root level
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://yourdomain.com")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

DEFAULT_SETTINGS = {
    "action": "decline",  # 'decline', 'ban', or 'approve_log'
    "guard_mode": True,   # If False, auto-approve all join requests
    "check_device": True,
    "check_ip": True,
    "check_avatar": True,
    "check_premium": True,
    "check_language": True,
    "log_languages": [],
    "check_fingerprint": True,
    "check_account_age": True,
    "min_account_age_months": 3,
    "avatar_min_count": 1,
    "questions_count": 1,  # How many random questions to ask per captcha
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