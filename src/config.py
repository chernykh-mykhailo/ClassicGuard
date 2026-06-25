import os
from dotenv import load_dotenv

# Load env variables from root level
load_dotenv(dotenv_path=os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://yourdomain.com")
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "")

DEFAULT_SETTINGS = {
    "action": "decline",  # 'decline' or 'ban'
    "guard_mode": True,   # If False, auto-approve all join requests
    "check_device": True,
    "check_ip": True,
    "check_avatar": True,
    "avatar_min_days": 3,
    "log_channel": "",    # ID of the channel for logs
    "contact_link": "",
    "decline_msg_captcha": "",  # Message when captcha failed
    "decline_msg_twink": "",   # Message when suspected twink (IP/avatar)
    "questions": [
        {"q": "Чий Крим?", "a": ["український", "україна", "україни"]},
        {"q": "Батько наш - ...?", "a": ["бандера"]},
        {"q": "Україна - це ...?", "a": ["європа", "понад усе"]}
    ]
}
