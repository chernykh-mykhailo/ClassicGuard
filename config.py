import os
import json

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://yourdomain.com")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "") # optional extra protection

SETTINGS_FILE = os.path.join(os.path.dirname(__file__), "settings.json")

DEFAULT_SETTINGS = {
    "action": "decline",  # 'decline' or 'ban'
    "check_device": True,
    "check_ip": True,
    "check_avatar": True,
    "avatar_min_days": 3,
    "questions": [
        {"q": "Чий Крим?", "a": ["український", "україна", "україни"]},
        {"q": "Батько наш - ...?", "a": ["бандера"]},
        {"q": "Україна ...?", "a": ["європа", "понад усе", "мати"]}
    ]
}

def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_SETTINGS, f, indent=4, ensure_ascii=False)
        return DEFAULT_SETTINGS
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_SETTINGS

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)
