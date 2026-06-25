import requests
from src.config import BOT_TOKEN

API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

def make_request(method: str, params: dict = None) -> dict:
    url = f"{API_URL}/{method}"
    try:
        resp = requests.post(url, json=params, timeout=10)
        return resp.json()
    except Exception as e:
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

def get_user_profile_photos(user_id: int, limit: int = 1):
    return make_request("getUserProfilePhotos", {"user_id": user_id, "limit": limit})

def send_message(chat_id: str | int, text: str, parse_mode: str = "HTML"):
    return make_request("sendMessage", {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode
    })
