import requests
import logging
from src.config import BOT_TOKEN

logger = logging.getLogger(__name__)

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def make_request(method: str, params: dict = None) -> dict:
    url = f"{API_URL}/{method}"
    try:
        resp = requests.post(url, json=params, timeout=10)
        result = resp.json()
        if not result.get("ok"):
            logger.warning(f"Telegram API error [{method}]: {result.get('description')} | params={params}")
        return result
    except Exception as e:
        logger.error(f"Request exception [{method}]: {e}")
        return {"ok": False, "description": str(e)}

def set_webhook(url: str):
    return make_request("setWebhook", {"url": url, "allowed_updates": ["chat_join_request", "message"]})

def send_chat_join_request_web_app(chat_join_request_query_id: str, web_app_url: str):
    return make_request("sendChatJoinRequestWebApp", {
        "chat_join_request_query_id": chat_join_request_query_id,
        "web_app_url": web_app_url
    })

def answer_chat_join_request_query(chat_join_request_query_id: str, result: str):
    return make_request("answerChatJoinRequestQuery", {
        "chat_join_request_query_id": chat_join_request_query_id,
        "result": result
    })

def approve_chat_join_request(chat_id: int, user_id: int):
    return make_request("approveChatJoinRequest", {
        "chat_id": chat_id,
        "user_id": user_id
    })

def decline_chat_join_request(chat_id: int, user_id: int):
    return make_request("declineChatJoinRequest", {
        "chat_id": chat_id,
        "user_id": user_id
    })

def ban_chat_member(chat_id: int, user_id: int):
    return make_request("banChatMember", {
        "chat_id": chat_id,
        "user_id": user_id
    })

def get_user_profile_photos(user_id: int, limit: int = 1):
    return make_request("getUserProfilePhotos", {"user_id": user_id, "limit": limit})

def send_message(chat_id: str | int, text: str, parse_mode: str = "HTML", reply_markup: dict = None, message_thread_id: int = None):
    params = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    }
    if reply_markup:
        params["reply_markup"] = reply_markup
    if message_thread_id:
        params["message_thread_id"] = message_thread_id
    return make_request("sendMessage", params)

def get_chat_member(chat_id: str | int, user_id: int):
    return make_request("getChatMember", {"chat_id": chat_id, "user_id": user_id})

def set_my_commands():
    commands = [
        {"command": "id", "description": "Отримати ID чату та користувача"},
        {"command": "settings", "description": "Налаштування ClassicGuard"}
    ]
    return make_request("setMyCommands", {"commands": commands})
