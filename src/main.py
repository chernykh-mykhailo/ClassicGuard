import hashlib
import hmac
import urllib.parse
import logging
import random
from fastapi import FastAPI, Request, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any
import time
import os

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s"
)
logger = logging.getLogger(__name__)

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

bot_username = "ClassicGuard_Bot"

# Initialize database on startup
@app.on_event("startup")
def startup_event():
    global bot_username
    database.init_db()
    if config.BOT_TOKEN != "YOUR_BOT_TOKEN_HERE":
        bot_api.set_my_commands()
        me_resp = bot_api.make_request("getMe")
        if me_resp.get("ok"):
            bot_username = me_resp.get("result", {}).get("username", "ClassicGuard_Bot")
        if "yourdomain.com" not in config.WEBAPP_URL:
            webhook_url = f"{config.WEBAPP_URL.rstrip('/')}/webhook"
            bot_api.set_webhook(webhook_url)

active_queries = {}     # query_id -> {chat_id, user_id, ...}  (new API with query_id)
fallback_queries = {}  # user_id -> {chat_id, user_id, ...}  (old flow without query_id)
ip_history = {}

class SettingsModel(BaseModel):
    action: str
    guard_mode: bool = True
    check_device: bool
    check_ip: bool
    check_avatar: bool
    check_premium: bool = True
    check_language: bool = True
    check_fingerprint: bool = True
    avatar_min_count: int = 1
    log_channel: str
    contact_link: str = ""
    decline_msg_captcha: str = ""
    decline_msg_twink: str = ""
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
        message_thread_id = msg.get("message_thread_id")
        
        if chat.get("type") in ["group", "supergroup"]:
            database.get_chat_settings(chat_id)
        
        # Support command matches even if they include bot username, e.g. /id@botname
        command = text.split("@")[0].split()[0] if text.startswith("/") else text
        
        if command in ["/get_id", "/id"]:
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
            bot_api.send_message(chat_id, response_text, message_thread_id=message_thread_id)
        elif command.startswith("/start"):
            args = text.split()
            if len(args) > 1 and args[1].startswith("settings_"):
                target_chat_id = int(args[1].split("_")[1])
                user_id = user.get("id")
                member_resp = bot_api.get_chat_member(target_chat_id, user_id)
                status = member_resp.get("result", {}).get("status", "")
                if status in ["creator", "administrator"]:
                    web_app_url = f"{config.WEBAPP_URL.rstrip('/')}/static/admin.html?chat_id={target_chat_id}"
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "⚙️ Відкрити налаштування чату",
                                    "web_app": {"url": web_app_url}
                                }
                            ]
                        ]
                    }
                    bot_api.send_message(chat_id, f"Ось посилання для налаштування чату <code>{target_chat_id}</code>:", reply_markup=reply_markup)
                else:
                    bot_api.send_message(chat_id, "⚠️ Ви повинні бути адміністратором цієї групи, щоб змінювати її налаштування.")
            else:
                response_text = (
                    "👋 <b>Вітаю! Я бот ClassicGuard.</b>\n\n"
                    "Я допомагаю захищати чати від спам-ботів та твінк-акаунтів за допомогою перевірок та капчі.\n\n"
                    "ℹ️ <b>Доступні команди:</b>\n"
                    "• <code>/id</code> або <code>/get_id</code> — дізнатись ID чату та ваш ID.\n"
                    "• <code>/settings</code> або <code>/config</code> — відкрити веб-панель налаштувань (лише для адмінів у чаті групи)."
                )
                bot_api.send_message(chat_id, response_text, message_thread_id=message_thread_id)
        elif command in ["/settings", "/config"]:
            user_id = user.get("id")
            if chat.get("type") in ["group", "supergroup"]:
                member_resp = bot_api.get_chat_member(chat_id, user_id)
                status = member_resp.get("result", {}).get("status", "")
                if status in ["creator", "administrator"]:
                    # In group chats, send a link redirecting to the bot's PM
                    deep_link = f"https://t.me/{bot_username}?start=settings_{chat_id}"
                    reply_markup = {
                        "inline_keyboard": [
                            [
                                {
                                    "text": "⚙️ Перейти в ПП для налаштування",
                                    "url": deep_link
                                }
                            ]
                        ]
                    }
                    bot_api.send_message(chat_id, "Для налаштування бота в цій групі, перейдіть в особисті повідомлення за кнопкою нижче:", reply_markup=reply_markup, message_thread_id=message_thread_id)
                else:
                    bot_api.send_message(chat_id, "⚠️ Ця команда доступна лише адміністраторам групи.", message_thread_id=message_thread_id)
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
        chat_id = chat.get("id")
        user_id = user.get("id")
        username = user.get("username", "") or user.get("first_name", "")

        # Full payload log for debugging
        import json as _json
        logger.info(f"chat_join_request FULL: {_json.dumps(req, ensure_ascii=False)}")

        database.log_verification_start(chat_id, user_id, username)
        chat_settings = database.get_chat_settings(chat_id)
        guard_mode = chat_settings.get("guard_mode", True)

        if not guard_mode:
            logger.info(f"Guard mode off for chat {chat_id}, auto-approving user {user_id}")
            bot_api.approve_chat_join_request(chat_id, user_id)
            return {"ok": True}

        log_chan = chat_settings.get("log_channel")
        user_mention = f"@{user.get('username')}" if user.get('username') else f"<a href='tg://user?id={user_id}'>{user.get('first_name')}</a>"
        if log_chan:
            bot_api.send_message(log_chan, f"👤 <b>Новий запит на вхід</b> від {user_mention} (ID: <code>{user_id}</code>) у чат <b>{chat.get('title', chat_id)}</b>.")

        if not query_id:
            # query_id відсутній — бот ще не є guard bot для цього чату
            # або клієнт старий. Просто логуємо, нічого не робимо (Telegram сам показує кнопки адміну)
            logger.warning(f"No query_id in chat_join_request for user {user_id} in chat {chat_id}. Bot may not be guard bot yet.")
            return {"ok": True}

        # Bot API 10.1+: надсилаємо Web App прямо в діалог join request
        active_queries[query_id] = {
            "chat_id": chat_id,
            "user_id": user_id,
            "timestamp": time.time(),
            "user_name": username,
        }
        web_app_url = f"{config.WEBAPP_URL.rstrip('/')}/static/index.html?query_id={query_id}"
        result = bot_api.send_chat_join_request_web_app(query_id, web_app_url)
        logger.info(f"sendChatJoinRequestWebApp result: {result}")

    return {"ok": True}


@app.get("/api/questions")
async def get_questions(query_id: str = None, session: str = None):
    if query_id:
        if query_id not in active_queries:
            raise HTTPException(status_code=400, detail="Invalid or expired query_id")
        chat_id = active_queries[query_id]["chat_id"]
    elif session:
        if session not in fallback_queries:
            raise HTTPException(status_code=400, detail="Invalid or expired session")
        chat_id = fallback_queries[session]["chat_id"]
    else:
        raise HTTPException(status_code=400, detail="query_id or session required")

    settings = database.get_chat_settings(chat_id)
    all_qs = settings.get("questions", [])
    if not all_qs:
        raise HTTPException(status_code=404, detail="No questions configured")

    # Вибираємо одне випадкове питання
    chosen_idx = random.randrange(len(all_qs))
    chosen = all_qs[chosen_idx]

    if chosen.get("type") == "emoji":
        correct_emoji = chosen["correct"]
        distractors = list(chosen.get("distractors", []))
        # Build full emoji list: correct + distractors, then shuffle
        all_emojis = [correct_emoji] + distractors
        random.shuffle(all_emojis)
        correct_pos = all_emojis.index(correct_emoji)

        # Store correct position in session
        store = active_queries if query_id else fallback_queries
        key = query_id if query_id else session
        store[key]["emoji_correct"] = {str(chosen_idx): correct_pos}

        return {"questions": [{
            "id": chosen_idx,
            "type": "emoji",
            "q": chosen["q"],
            "emojis": all_emojis
        }]}
    else:
        return {"questions": [{"id": chosen_idx, "q": chosen["q"], "type": "text"}]}

@app.post("/api/verify")
async def verify_user(request: Request):
    data = await request.json()
    query_id = data.get("query_id")
    session = data.get("session")
    answers = data.get("answers", {})
    device_info = data.get("device_info", "")
    client_ip = request.client.host

    # Resolve query_data and mode
    if query_id and query_id in active_queries:
        query_data = active_queries[query_id]
        mode = "query"
    elif session and session in fallback_queries:
        query_data = fallback_queries[session]
        mode = "fallback"
    else:
        raise HTTPException(status_code=400, detail="Invalid or expired session")

    user_id = query_data["user_id"]
    chat_id = query_data["chat_id"]
    settings = database.get_chat_settings(chat_id)

    def do_decline():
        act = settings.get("action")
        if mode == "query":
            if act == "approve_log":
                bot_api.answer_chat_join_request_query(query_id, "approve")
            else:
                bot_api.answer_chat_join_request_query(query_id, "decline")
        else:
            if act == "ban":
                bot_api.ban_chat_member(chat_id, user_id)
            elif act == "approve_log":
                bot_api.approve_chat_join_request(chat_id, user_id)
            else:
                bot_api.decline_chat_join_request(chat_id, user_id)
        if mode == "query":
            active_queries.pop(query_id, None)
        else:
            fallback_queries.pop(session, None)

    def do_approve():
        if mode == "query":
            bot_api.answer_chat_join_request_query(query_id, "approve")
            active_queries.pop(query_id, None)
        else:
            bot_api.approve_chat_join_request(chat_id, user_id)
            fallback_queries.pop(session, None)

    DEFAULT_MSGS = {
        "captcha": "На жаль, ваш запит на вступ було відхилено.\n\nЯкщо ви вважаєте це помилкою — зверніться до адміністратора чату.",
        "twink": "На жаль, ваш запит на вступ було відхилено.\n\nЯкщо ви вважаєте це помилкою — зверніться до адміністратора чату.",
    }

    def notify_declined(reason: str = "captcha"):
        key = "decline_msg_captcha" if reason == "captcha" else "decline_msg_twink"
        custom = settings.get(key, "").strip()
        contact = settings.get("contact_link", "").strip()
        msg = custom if custom else DEFAULT_MSGS[reason]
        if contact:
            msg += f"\n\nЗв'яжіться: {contact}"
        bot_api.send_message(user_id, msg)

    # 1. Check Captcha Answers
    emoji_correct = query_data.get("emoji_correct", {})
    correct_count = 0
    checked = 0

    for q_idx_str, correct_pos in emoji_correct.items():
        # Emoji question — check selected index
        user_sel = answers.get(q_idx_str)
        checked += 1
        if user_sel is not None and int(user_sel) == correct_pos:
            correct_count += 1

    all_qs = settings.get("questions", [])
    for idx, q_data in enumerate(all_qs):
        idx_str = str(idx)
        if idx_str in emoji_correct:
            continue  # already checked above
        if idx_str not in answers:
            continue  # question not shown this session
        checked += 1
        if q_data.get("type") == "emoji":
            pass  # handled above
        else:
            user_ans = str(answers.get(idx_str, "")).strip().lower()
            correct_options = [str(a).lower().strip() for a in q_data.get("a", [])]
            if any(opt in user_ans for opt in correct_options):
                correct_count += 1

    if checked == 0 or correct_count < checked:
        act = settings.get("action")
        if act == "approve_log":
            status = "declined_but_approved"
        elif act == "ban":
            status = "banned"
        else:
            status = "declined"
        database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
        log_chan = settings.get("log_channel")
        if log_chan:
            if act == "approve_log":
                action_ua = "✅ Прийнято (з логуванням)"
            else:
                action_ua = "Забанено" if act == "ban" else "Відхилено"
            bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (Капча)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Неправильні відповіді на капчу.")
        do_decline()
        if act != "approve_log":
            notify_declined("captcha")
        return {"success": False, "reason": "Перевірку не пройдено."}

    # 2. Check Twink / Alt account factors
    if settings["check_ip"]:
        if client_ip in ip_history and ip_history[client_ip] != user_id:
            act = settings.get("action")
            if act == "approve_log":
                status = "declined_but_approved_ip_match"
            elif act == "ban":
                status = "banned_ip_match"
            else:
                status = "declined_ip_match"
            database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
            log_chan = settings.get("log_channel")
            if log_chan:
                if act == "approve_log":
                    action_ua = "✅ Прийнято (з логуванням)"
                else:
                    action_ua = "Забанено" if act == "ban" else "Відхилено"
                bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (Збіг IP)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Твінк (однаковий IP з іншим користувачем).")
            do_decline()
            if act != "approve_log":
                notify_declined("twink")
            return {"success": False, "reason": "Перевірку не пройдено."}
        ip_history[client_ip] = user_id

    if settings["check_avatar"]:
        min_count = settings.get("avatar_min_count", 1)
        if min_count > 0:
            photos_resp = bot_api.get_user_profile_photos(user_id, limit=min_count)
            if photos_resp.get("ok"):
                photos = photos_resp.get("result", {}).get("photos", [])
                if len(photos) < min_count:
                    act = settings.get("action")
                    if act == "approve_log":
                        status = "declined_but_approved_no_avatar"
                    elif act == "ban":
                        status = "banned_no_avatar"
                    else:
                        status = "declined_no_avatar"
                    database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
                    log_chan = settings.get("log_channel")
                    if log_chan:
                        if act == "approve_log":
                            action_ua = "✅ Прийнято (з логуванням)"
                        else:
                            action_ua = "Забанено" if act == "ban" else "Відхилено"
                        bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (Без ави)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Відсутній аватар (підозра на твінк).")
                    do_decline()
                    if act != "approve_log":
                        notify_declined("twink")
                    return {"success": False, "reason": "Перевірку не пройдено."}

    # 3. Collect fingerprint data (Premium, language, device fingerprint)
    fingerprint = data.get("fingerprint", {})
    is_premium = fingerprint.get("is_premium", False)
    lang_code = fingerprint.get("language_code", "")
    fp_canvas = fingerprint.get("canvas", "")
    fp_webgl = fingerprint.get("webgl", "")
    fp_screen = fingerprint.get("screen", "")
    fp_timezone = fingerprint.get("timezone", "")
    fp_platform = fingerprint.get("platform", "")

    # Store fingerprint in query data for future cross-checking
    query_data["fingerprint"] = {
        "is_premium": is_premium,
        "language_code": lang_code,
        "canvas": fp_canvas,
        "webgl": fp_webgl,
        "screen": fp_screen,
        "timezone": fp_timezone,
        "platform": fp_platform,
    }

    # Log suspicious cases but don't block (too aggressive to block)
    log_chan = settings.get("log_channel")
    if log_chan and settings.get("check_premium", True):
        if not is_premium:
            bot_api.send_message(log_chan, f"ℹ️ <b>Без Premium</b>: (ID: <code>{user_id}</code>). Користувач без Telegram Premium.")
    if log_chan and settings.get("check_language", True):
        if lang_code and lang_code not in ["uk", "ru", "be", "en"]:
            bot_api.send_message(log_chan, f"ℹ️ <b>Підозріла мова</b>: (ID: <code>{user_id}</code>). Мова інтерфейсу: {lang_code}.")

    database.log_verification_result(chat_id, user_id, client_ip, device_info, "approved", answers)
    log_chan = settings.get("log_channel")
    if log_chan:
        bot_api.send_message(log_chan, f"✅ <b>Користувач схвалений</b> (ID: <code>{user_id}</code>).\nВсі перевірки пройдено успішно!")
    do_approve()
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
