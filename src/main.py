import hashlib
import hmac
import urllib.parse
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import time
import os

from src import config
from src import bot_api
from src import database

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    database.init_db()
    if config.BOT_TOKEN != "YOUR_BOT_TOKEN_HERE" and "yourdomain.com" not in config.WEBAPP_URL:
        webhook_url = f"{config.WEBAPP_URL.rstrip('/')}/webhook"
        bot_api.set_webhook(webhook_url)

active_queries = {}
ip_history = {}

class SettingsModel(BaseModel):
    action: str
    check_device: bool
    check_ip: bool
    check_avatar: bool
    avatar_min_days: int
    log_channel: str
    questions: List[Dict[str, Any]]

@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    
    if "message" in data:
        msg = data["message"]
        text = msg.get("text", "").strip()
        chat = msg.get("chat", {})
        chat_id = chat.get("id")
        user = msg.get("from", {})
        
        if text.startswith("/get_id") or text.startswith("/id"):
            reply_to = msg.get("reply_to_message")
            if reply_to:
                replied_user = reply_to.get("from", {})
                replied_id = replied_user.get("id")
                username_str = f" (@{replied_user.get('username')})" if replied_user.get('username') else ""
                response_text = (
                    f"🏢 <b>ID цього чату:</b> <code>{chat_id}</code>\n"
                    f"👤 <b>Ваш ID:</b> <code>{user.get('id')}</code>\n"
                    f"👉 <b>ID реплайнутого користувача:</b> <code>{replied_id}</code>{username_str}"
                )
            else:
                response_text = (
                    f"🏢 <b>ID цього чату:</b> <code>{chat_id}</code>\n"
                    f"👤 <b>Ваш ID:</b> <code>{user.get('id')}</code>"
                )
            bot_api.send_message(chat_id, response_text)
        elif text.startswith("/start"):
            response_text = (
                "👋 <b>Вітаю! Я бот ClassicGuard.</b>\n\n"
                "Я допомагаю захищати чати від спам-ботів та твінк-акаунтів за допомогою перевірок та капчі.\n\n"
                "ℹ️ <b>Доступні команди:</b>\n"
                "• <code>/id</code> або <code>/get_id</code> — дізнатись ID чату та ваш ID.\n"
                "• <code>/settings</code> або <code>/config</code> — відкрити веб-панель налаштувань (лише для адмінів у чаті групи)."
            )
            bot_api.send_message(chat_id, response_text)
        elif text.startswith("/settings") or text.startswith("/config"):
            user_id = user.get("id")
            if chat.get("type") in ["group", "supergroup"]:
                member_resp = bot_api.get_chat_member(chat_id, user_id)
                status = member_resp.get("result", {}).get("status", "")
                if status in ["creator", "administrator"]:
                    web_app_url = f"{config.WEBAPP_URL.rstrip('/')}/static/admin.html?chat_id={chat_id}"
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "⚙️ Відкрити налаштування",
                                    "web_app": {"url": web_app_url}
                                }
                            ]
                        ]
                    }
                    bot_api.send_message(chat_id, "Натисніть кнопку нижче, щоб відкрити панель налаштувань для цієї групи:", reply_markup=reply_markup)
                else:
                    bot_api.send_message(chat_id, "⚠️ Ця команда доступна лише адміністраторам групи.")
            else:
                # Private chat setting mode
                web_app_url = f"{config.WEBAPP_URL.rstrip('/')}/static/admin.html"
                reply_markup = {
                    "inline_keyboard": [
                        [
                            {
                                "text": "⚙️ Відкрити панель керування",
                                "web_app": {"url": web_app_url}
                            }
                        ]
                    ]
                }
                bot_api.send_message(chat_id, "Натисніть кнопку нижче, щоб налаштувати ботів для ваших чатів:", reply_markup=reply_markup)

    elif "chat_join_request" in data:
        req = data["chat_join_request"]
        query_id = req.get("query_id")
        user = req.get("from", {})
        chat = req.get("chat", {})
        
        if query_id:
            chat_id = chat.get("id")
            user_id = user.get("id")
            username = user.get("username", "") or user.get("first_name", "")
            
            active_queries[query_id] = {
                "chat_id": chat_id,
                "user_id": user_id,
                "timestamp": time.time(),
                "user_name": username
            }
            # Log verification start
            database.log_verification_start(chat_id, user_id, username)
            
            # Send log channel notification if configured
            chat_settings = database.get_chat_settings(chat_id)
            log_chan = chat_settings.get("log_channel")
            if log_chan:
                user_mention = f"@{user.get('username')}" if user.get('username') else f"<a href='tg://user?id={user_id}'>{user.get('first_name')}</a>"
                bot_api.send_message(log_chan, f"👤 <b>Новий запит на вхід</b> від {user_mention} (ID: <code>{user_id}</code>) у чат <b>{chat.get('title', chat_id)}</b>. Очікуємо проходження капчі...")

            web_app_url = f"{config.WEBAPP_URL.rstrip('/')}/static/index.html?query_id={query_id}"
            bot_api.send_chat_join_request_web_app(query_id, web_app_url)
            
    return {"ok": True}

@app.get("/api/questions")
async def get_questions(query_id: str):
    if query_id not in active_queries:
        raise HTTPException(status_code=400, detail="Invalid or expired query_id")
    
    chat_id = active_queries[query_id]["chat_id"]
    settings = database.get_chat_settings(chat_id)
    qs = [{"id": i, "q": q["q"]} for i, q in enumerate(settings["questions"])]
    return {"questions": qs}

@app.post("/api/verify")
async def verify_user(request: Request):
    data = await request.json()
    query_id = data.get("query_id")
    answers = data.get("answers", {})
    device_info = data.get("device_info", "")
    client_ip = request.client.host
    
    if not query_id or query_id not in active_queries:
        raise HTTPException(status_code=400, detail="Invalid or expired query_id")
        
    query_data = active_queries[query_id]
    user_id = query_data["user_id"]
    chat_id = query_data["chat_id"]
    
    settings = database.get_chat_settings(chat_id)
    
    # 1. Check Captcha Answers
    correct_count = 0
    for idx, q_data in enumerate(settings["questions"]):
        user_ans = str(answers.get(str(idx), "")).strip().lower()
        correct_options = [str(ans).lower().strip() for ans in q_data["a"]]
        if any(opt in user_ans for opt in correct_options):
            correct_count += 1
            
    if correct_count < len(settings["questions"]):
        status = "banned" if settings["action"] == "ban" else "declined"
        database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
        log_chan = settings.get("log_channel")
        if log_chan:
            action_ua = "Забанено" if settings["action"] == "ban" else "Відхилено"
            bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (Капча)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Неправильні відповіді на капчу.")
        bot_api.answer_chat_join_request_query(query_id, "decline")
        return {"success": False, "reason": "Неправильні відповіді на капчу."}
        
    # 2. Check Twink / Alt account factors
    if settings["check_ip"]:
        if client_ip in ip_history and ip_history[client_ip] != user_id:
            status = "banned" if settings["action"] == "ban" else "declined"
            database.log_verification_result(chat_id, user_id, client_ip, device_info, f"{status}_ip_match", answers)
            log_chan = settings.get("log_channel")
            if log_chan:
                action_ua = "Забанено" if settings["action"] == "ban" else "Відхилено"
                bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (Збіг IP)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Твінк (однаковий IP з іншим користувачем).")
            bot_api.answer_chat_join_request_query(query_id, "decline")
            return {"success": False, "reason": "Виявлено підозрілу активність (збіг IP)."}
        ip_history[client_ip] = user_id
        
    if settings["check_avatar"]:
        photos_resp = bot_api.get_user_profile_photos(user_id)
        if photos_resp.get("ok"):
            photos = photos_resp.get("result", {}).get("photos", [])
            if len(photos) == 0:
                status = "banned" if settings["action"] == "ban" else "declined"
                database.log_verification_result(chat_id, user_id, client_ip, device_info, f"{status}_no_avatar", answers)
                log_chan = settings.get("log_channel")
                if log_chan:
                    action_ua = "Забанено" if settings["action"] == "ban" else "Відхилено"
                    bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (Без ави)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Відсутній аватар (підозра на твінк).")
                bot_api.answer_chat_join_request_query(query_id, "decline")
                return {"success": False, "reason": "У вас відсутня аватарка."}
                
    database.log_verification_result(chat_id, user_id, client_ip, device_info, "approved", answers)
    log_chan = settings.get("log_channel")
    if log_chan:
        bot_api.send_message(log_chan, f"✅ <b>Користувач схвалений</b> (ID: <code>{user_id}</code>).\nВсі перевірки пройдено успішно!")
    bot_api.answer_chat_join_request_query(query_id, "approve")
    active_queries.pop(query_id, None)
    return {"success": True}

@app.get("/api/settings")
async def get_settings(chat_id: int):
    return database.get_chat_settings(chat_id)

@app.post("/api/settings")
async def update_settings(chat_id: int, settings: SettingsModel):
    database.save_chat_settings(chat_id, settings.model_dump())
    log_chan = settings.log_channel
    if log_chan:
        bot_api.send_message(log_chan, f"⚙️ <b>Налаштування ClassicGuard оновлено</b> для чату <code>{chat_id}</code>.")
    return {"success": True}

@app.get("/api/admin/chats")
async def get_admin_chats(user_id: int):
    chats = database.get_all_chats()
    admin_chats = []
    for c_id in chats:
        member_resp = bot_api.get_chat_member(c_id, user_id)
        if member_resp.get("ok"):
            status = member_resp.get("result", {}).get("status", "")
            if status in ["creator", "administrator"]:
                chat_resp = bot_api.make_request("getChat", {"chat_id": c_id})
                title = chat_resp.get("result", {}).get("title", f"Група {c_id}")
                admin_chats.append({"id": c_id, "title": title})
    return {"chats": admin_chats}

# Serve static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    return {"status": "ClassicGuard Bot is running"}
