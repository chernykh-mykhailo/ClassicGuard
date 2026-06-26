import hashlib
import hmac
import urllib.parse
import logging
import random
from datetime import datetime
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
from src import userbot as userbot_module

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
    log_languages: List[str] = []
    check_fingerprint: bool = True
    check_account_age: bool = True
    min_account_age_months: int = 3
    avatar_min_count: int = 1
    questions_count: int = 1
    check_osint: bool = False
    osint_action: str = "log"
    check_cas: bool = False
    cas_action: str = "block"
    check_global_spammer_db: bool = False
    check_ban_commands: bool = True
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
        
        elif command == "/ban":
            user_id = user.get("id")
            if chat.get("type") not in ["group", "supergroup"]:
                bot_api.send_message(chat_id, "⚠️ Команда /ban доступна лише в групах.")
                return {"ok": True}
            
            # Check if user is admin
            member_resp = bot_api.get_chat_member(chat_id, user_id)
            status = member_resp.get("result", {}).get("status", "")
            if status not in ["creator", "administrator"]:
                bot_api.send_message(chat_id, "⚠️ Лише адміністратори можуть використовувати /ban")
                return {"ok": True}
            
            # Check if ban commands are enabled in settings
            chat_settings = database.get_chat_settings(chat_id)
            if not chat_settings.get("check_ban_commands", True):
                bot_api.send_message(chat_id, "⚠️ Команди /ban вимкнені в налаштуваннях цього чату.")
                return {"ok": True}
            
            # Get target user from reply
            reply_to = msg.get("reply_to_message")
            if not reply_to:
                bot_api.send_message(chat_id, "⚠️ Використання: /ban [переман|спам] [причина]\nАбо реплай на повідомлення користувача + /ban [переман|спам] [причина]")
                return {"ok": True}
            
            target_user = reply_to.get("from", {})
            target_id = target_user.get("id")
            target_username = target_user.get("username", "") or target_user.get("first_name", "Unknown")
            
            # Parse command: /ban [time] [переман|спам] [reason...] OR /ban [переман|спам] [reason...]
            # Time formats: 100 (days), 1m (minutes), 2h (hours), 7d (days)
            args = text.split(maxsplit=1)  # Split into: ['/ban', 'rest...']
            rest = args[1] if len(args) > 1 else ""
            
            # Parse time specification (optional)
            until_date = None  # None = permanent ban
            time_parts = rest.split(maxsplit=1)
            time_str = time_parts[0]
            
            # Check if first part is a time specification
            if time_str and not any(keyword in time_str.lower() for keyword in ["переман", "спам"]):
                # Try to parse time
                import re
                match = re.match(r'^(\d+)([mhd]?)$', time_str, re.IGNORECASE)
                if match:
                    amount = int(match.group(1))
                    unit = match.group(2).lower() if match.group(2) else 'd'  # Default to days
                    
                    # Calculate until_date (Unix timestamp)
                    import time as time_module
                    now = int(time_module.time())
                    
                    if unit == 'm':  # minutes
                        until_date = now + (amount * 60)
                    elif unit == 'h':  # hours
                        until_date = now + (amount * 3600)
                    elif unit == 'd':  # days
                        until_date = now + (amount * 86400)
                    else:  # no unit = days
                        until_date = now + (amount * 86400)
                    
                    # Remove time from rest
                    rest = time_parts[1] if len(time_parts) > 1 else ""
            
            # Check if remaining text contains переман or спам
            reason_lower = rest.lower()
            
            if "переман" in reason_lower:
                # Add to local spammer database
                database.report_spammer(target_id, chat_id, user_id, f"переман: {rest}")
                
                # Ban with time
                ban_result = bot_api.ban_chat_member(chat_id, target_id, until_date)
                
                if ban_result.get("ok"):
                    if until_date:
                        # Calculate duration for message
                        import time as time_module
                        duration_secs = until_date - int(time_module.time())
                        days = duration_secs // 86400
                        hours = (duration_secs % 86400) // 3600
                        minutes = (duration_secs % 3600) // 60
                        
                        if days > 0:
                            duration_str = f"{days} дн."
                        elif hours > 0:
                            duration_str = f"{hours} год."
                        else:
                            duration_str = f"{minutes} хв."
                        
                        bot_api.send_message(chat_id, f"✅ Користувача <b>{target_username}</b> (ID: <code>{target_id}</code>) забанено на {duration_str}.\n<b>Причина:</b> {rest}")
                    else:
                        bot_api.send_message(chat_id, f"✅ Користувача <b>{target_username}</b> (ID: <code>{target_id}</code>) забанено назавжди.\n<b>Причина:</b> {rest}")
                else:
                    bot_api.send_message(chat_id, f"❌ Помилка при бані користувача. Можливо, він вже забанений або не в чаті.")
            
            elif "спам" in reason_lower:
                # Report to CAS (if available)
                bot_api.send_message(chat_id, f"🔄 Звіт в CAS для <b>{target_username}</b> (ID: <code>{target_id}</code>)...\n<b>Причина:</b> {rest}")
                
                # Try to report via CAS (note: CAS doesn't have public report API, so we log it)
                # In future, could integrate with SpamWatch or other services
                cas_result = await userbot_module.cas_check(target_id)
                if cas_result.get("is_banned"):
                    bot_api.send_message(chat_id, f"ℹ️ Користувач вже є в базі CAS (ID: {cas_result.get('cas_id')})")
                else:
                    # Log as spam report locally
                    database.report_spammer(target_id, chat_id, user_id, f"спам: {rest}")
                    bot_api.send_message(chat_id, f"✅ Звіт збережено. Користувач не в базі CAS, але звіт записано в локальну базу.\n\n💡 Примітка: CAS не має публічного API для додавання. Для реального спам-репорту використовуйте @SpamBot або @SpamWatchBot.")
            
            else:
                # No trigger word found
                bot_api.send_message(chat_id, "⚠️ Не вказано тип звіту. Використовуйте:\n/ban [час] [переман|спам] [причина]\n\nПриклади:\n/ban 100 переман спам\n/ban 1m спам реклама\n/ban 2h переман обман\n/ban переман (назавжди)\n/ban спам (назавжди)")

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

    questions_count = settings.get("questions_count", 1)
    if questions_count < 1:
        questions_count = 1
    if questions_count > len(all_qs):
        questions_count = len(all_qs)

    # Pick random questions without duplicates
    chosen_indices = random.sample(range(len(all_qs)), questions_count)
    result_questions = []
    store = active_queries if query_id else fallback_queries
    key = query_id if query_id else session

    for chosen_idx in chosen_indices:
        chosen = all_qs[chosen_idx]

        if chosen.get("type") == "emoji":
            correct_emoji = chosen["correct"]
            distractors = list(chosen.get("distractors", []))
            all_emojis = [correct_emoji] + distractors
            random.shuffle(all_emojis)
            correct_pos = all_emojis.index(correct_emoji)

            if "emoji_correct" not in store[key]:
                store[key]["emoji_correct"] = {}
            store[key]["emoji_correct"][str(chosen_idx)] = correct_pos

            result_questions.append({
                "id": chosen_idx,
                "type": "emoji",
                "q": chosen["q"],
                "emojis": all_emojis
            })
        else:
            choices = chosen.get("choices", [])
            if choices:
                # Multiple choice question — shuffle choices
                shuffled = list(choices)
                random.shuffle(shuffled)
                result_questions.append({
                    "id": chosen_idx,
                    "type": "choice",
                    "q": chosen["q"],
                    "choices": shuffled
                })
            else:
                # Free text input
                result_questions.append({
                    "id": chosen_idx,
                    "q": chosen["q"],
                    "type": "text"
                })

    return {"questions": result_questions}

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

    def send_log(msg: str):
        log_chan = settings.get("log_channel")
        if log_chan:
            bot_api.send_message(log_chan, msg)
        else:
            # Fallback: send to chat owner PM
            try:
                chat_info = bot_api.make_request("getChat", {"chat_id": chat_id})
                if chat_info.get("ok"):
                    owner_id = chat_info.get("result", {}).get("id")
                    if owner_id:
                        bot_api.send_message(owner_id, f"📋 <b>Лог ClassicGuard</b>\n{msg}")
            except Exception as e:
                logger.warning(f"Failed to send fallback log to owner: {e}")

    def do_decline(reason: str = ""):
        act = settings.get("action")
        if mode == "query":
            if act == "approve_log":
                bot_api.answer_chat_join_request_query(query_id, "approve")
            else:
                bot_api.answer_chat_join_request_query(query_id, "decline")
        else:
            if act == "ban":
                bot_api.ban_chat_member(chat_id, user_id)
                # Auto-report to spammer database
                if settings.get("check_global_spammer_db", False):
                    database.report_spammer(user_id, chat_id, user_id, f"Auto-banned: {reason}")
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

    all_qs = settings.get("questions", [])
    for idx, q_data in enumerate(all_qs):
        idx_str = str(idx)
        if idx_str not in answers:
            continue  # question not shown this session
        checked += 1

        q_type = q_data.get("type", "text")

        if q_type == "emoji":
            correct_pos = emoji_correct.get(idx_str)
            user_sel = answers.get(idx_str)
            if correct_pos is not None and user_sel is not None and int(user_sel) == int(correct_pos):
                correct_count += 1
        elif q_type == "choice":
            # Multiple choice — answer is the selected choice text
            user_ans = str(answers.get(idx_str, "")).strip().lower()
            correct_options = [str(a).lower().strip() for a in q_data.get("a", [])]
            if any(opt in user_ans for opt in correct_options):
                correct_count += 1
        else:
            # Free text input
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
        if act == "approve_log":
            action_ua = "✅ Прийнято (з логуванням)"
        else:
            action_ua = "Забанено" if act == "ban" else "Відхилено"
        send_log(f"❌ <b>Перевірку провалено (Капча)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Неправильні відповіді на капчу.")
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
            if act == "approve_log":
                action_ua = "✅ Прийнято (з логуванням)"
            else:
                action_ua = "Забанено" if act == "ban" else "Відхилено"
            send_log(f"❌ <b>Перевірку провалено (Збіг IP)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Твінк (однаковий IP з іншим користувачем).")
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
                        send_log(f"❌ <b>Перевірку провалено (Без ави)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Відсутній аватар (підозра на твінк).")
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
        log_langs = settings.get("log_languages", [])
        if lang_code and lang_code in log_langs:
            bot_api.send_message(log_chan, f"⚠️ <b>Цільова мова</b>: (ID: <code>{user_id}</code>). Мова інтерфейсу: {lang_code} (в списку відстеження).")

    # 6. Check Account Age (estimated from Telegram ID)
    if settings.get("check_account_age", True):
        min_months = settings.get("min_account_age_months", 3)
        # Approximate: Telegram started in Aug 2013 (~562M users by start of 2024).
        # Rough formula: user_id / rate_per_month ≈ months since telegram start
        # ~13M new IDs per month in recent years. Older IDs had slower growth.
        # Conservative estimate: newer IDs are larger numbers
        # Telegram launched Aug 2013, ~2013.66 years
        # By roughly estimating: (user_id / 13_000_000) gives approx months since ID 0
        if user_id > 0:
            approx_months = user_id // 13_000_000  # rough months since Telegram launch
            approx_years = approx_months // 12
            if user_id > 0 and approx_months < min_months:
                act = settings.get("action")
                if act == "approve_log":
                    status = "declined_but_approved_young_account"
                elif act == "ban":
                    status = "banned_young_account"
                else:
                    status = "declined_young_account"
                database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
                if act == "approve_log":
                    action_ua = "✅ Прийнято (з логуванням)"
                else:
                    action_ua = "Забанено" if act == "ban" else "Відхилено"
                send_log(f"❌ <b>Перевірку провалено (Молодий акаунт)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Акаунту менше ніж {min_months} міс. (приблизно {approx_months} міс.).")
                do_decline()
                if act != "approve_log":
                    notify_declined("twink")
                return {"success": False, "reason": "Перевірку не пройдено."}
            if log_chan:
                bot_api.send_message(log_chan, f"ℹ️ <b>Вік акаунта</b>: (ID: <code>{user_id}</code>). Приблизний вік: {approx_months} міс. ({approx_years} років).")

    # 6.5. Global Spammer Database Check
    if settings.get("check_global_spammer_db", False):
        spammer_status = database.check_spammer_status(user_id)
        if spammer_status.get("is_confirmed"):
            act = settings.get("action")
            if act == "approve_log":
                status = "declined_but_approved_spammer"
            elif act == "ban":
                status = "banned_spammer"
            else:
                status = "declined_spammer"
            database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
            send_log(f"❌ <b>Перевірку провалено (Global Spammer DB)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {'Забанено' if act == 'ban' else 'Відхилено'}.\n<b>Причина:</b> Користувач в базі спамерів ({spammer_status.get('reason', 'N/A')}).")
            do_decline()
            if act != "approve_log":
                notify_declined("twink")
            return {"success": False, "reason": "Перевірку не пройдено."}

    # 7. CAS Check (Combot Anti-Spam)
    if settings.get("check_cas", False):
        cas_result = await userbot_module.cas_check(user_id)
        if cas_result.get("is_banned"):
            act = settings.get("cas_action", "block")
            if act == "block":
                status = "banned_cas"
            elif act == "approve_log":
                status = "declined_but_approved_cas"
            else:
                status = "declined_cas"
            database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
            log_chan = settings.get("log_channel")
            if log_chan:
                if act == "approve_log":
                    action_ua = "✅ Прийнято (з логуванням)"
                elif act == "block":
                    action_ua = "Забанено"
                else:
                    action_ua = "Відхилено"
                bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (CAS)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> Знайдено в базі CAS (Combot Anti-Spam).\n📋 Reason: {cas_result.get('reason', 'N/A')}\n🆔 CAS ID: {cas_result.get('cas_id', 'N/A')}")
            do_decline()
            if act != "approve_log":
                notify_declined("twink")
            return {"success": False, "reason": "Перевірку не пройдено."}
        else:
            if not cas_result.get("error"):
                send_log(f"ℹ️ <b>CAS</b>: (ID: <code>{user_id}</code>). Чисто (не в базі CAS).")

    # 8. OSINT Check (via userbot)
    if settings.get("check_osint", False):
        osint_result = await userbot_module.osint_lookup(user_id)
        osint_flagged = False
        osint_reasons = []

        if osint_result.get("is_scam"):
            osint_flagged = True
            osint_reasons.append("Scam-позначка")
        if osint_result.get("is_fake"):
            osint_flagged = True
            osint_reasons.append("Fake-позначка")

        # Avatar spam detection
        avatar_spam_score = osint_result.get("avatar_spam_score", 0)
        avatar_count = osint_result.get("avatar_count", 0)
        avatar_dates = osint_result.get("avatar_dates", [])
        if avatar_spam_score >= 5:
            osint_flagged = True
            osint_reasons.append(f"Підозріла історія аватарок (score={avatar_spam_score}, count={avatar_count})")

        if osint_flagged:
            act = settings.get("osint_action", "log")
            if act == "block":
                status = "banned_osint"
            elif act == "approve_log":
                status = "declined_but_approved_osint"
            else:
                status = "declined_osint"
            database.log_verification_result(chat_id, user_id, client_ip, device_info, status, answers)
            log_chan = settings.get("log_channel")
            if log_chan:
                if act == "approve_log":
                    action_ua = "✅ Прийнято (з логуванням)"
                elif act == "block":
                    action_ua = "Забанено"
                else:
                    action_ua = "Відхилено"
                bot_api.send_message(log_chan, f"❌ <b>Перевірку провалено (OSINT)</b>: (ID: <code>{user_id}</code>).\n<b>Дія:</b> {action_ua}.\n<b>Причина:</b> {', '.join(osint_reasons)}.\n📊 <pre>{osint_result}</pre>")
            do_decline()
            if act != "approve_log":
                notify_declined("twink")
            return {"success": False, "reason": "Перевірку не пройдено."}
        else:
            if not osint_result.get("error"):
                send_log(f"ℹ️ <b>OSINT</b>: (ID: <code>{user_id}</code>). Чисто (нема scam/fake).")

    database.log_verification_result(chat_id, user_id, client_ip, device_info, "approved", answers)
    log_chan = settings.get("log_channel")
    log_msg = f"✅ <b>Користувач схвалений</b> (ID: <code>{user_id}</code>).\nВсі перевірки пройдено успішно!"
    
    if log_chan:
        bot_api.send_message(log_chan, log_msg)
    else:
        # Fallback: send to chat owner PM
        try:
            chat_info = bot_api.make_request("getChat", {"chat_id": chat_id})
            if chat_info.get("ok"):
                owner_id = chat_info.get("result", {}).get("id")
                if owner_id:
                    bot_api.send_message(owner_id, f"📋 <b>Лог ClassicGuard</b>\n{log_msg}")
        except Exception as e:
            logger.warning(f"Failed to send fallback log to owner: {e}")
    
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

# Spammer database API
@app.post("/api/spammer/report")
async def report_spammer(user_id: int, chat_id: int, banned_by: int, reason: str = ""):
    database.report_spammer(user_id, chat_id, banned_by, reason)
    
    # Check if should be confirmed
    status = database.check_spammer_status(user_id)
    if status.get("is_confirmed"):
        database.confirm_spammer(user_id, f"Confirmed: {status['report_count']} reports from {status['unique_chats']} chats by {status['unique_reporters']} reporters")
    
    return {"success": True, "status": status}

@app.get("/api/spammer/check")
async def check_spammer(user_id: int):
    status = database.check_spammer_status(user_id)
    return status

@app.get("/api/spammer/list")
async def list_spammers():
    with database.get_db() as conn:
        rows = conn.execute("""
            SELECT s.user_id, s.reason, s.confirmed_at, 
                   COUNT(r.id) as report_count,
                   COUNT(DISTINCT r.chat_id) as chat_count
            FROM confirmed_spammers s
            LEFT JOIN spammer_reports r ON s.user_id = r.user_id
            GROUP BY s.user_id
            ORDER BY s.confirmed_at DESC
        """).fetchall()
        return {"spammers": [dict(row) for row in rows]}

@app.get("/api/spammer/reports")
async def list_reports():
    with database.get_db() as conn:
        rows = conn.execute("""
            SELECT * FROM spammer_reports 
            ORDER BY timestamp DESC
            LIMIT 1000
        """).fetchall()
        return {"reports": [dict(row) for row in rows]}

@app.post("/api/spammer/confirm")
async def confirm_spammer_api(user_id: int, reason: str = ""):
    database.confirm_spammer(user_id, reason)
    return {"success": True}

@app.delete("/api/spammer/remove")
async def remove_spammer(user_id: int):
    with database.get_db() as conn:
        conn.execute("DELETE FROM confirmed_spammers WHERE user_id = ?", (user_id,))
        conn.execute("DELETE FROM spammer_reports WHERE user_id = ?", (user_id,))
        conn.commit()
    return {"success": True}

@app.get("/api/spammer/export")
async def export_spammer_db():
    with database.get_db() as conn:
        spammers = conn.execute("SELECT * FROM confirmed_spammers").fetchall()
        reports = conn.execute("SELECT * FROM spammer_reports").fetchall()
        return {
            "spammers": [dict(row) for row in spammers],
            "reports": [dict(row) for row in reports],
            "exported_at": datetime.now().isoformat()
        }

@app.post("/api/spammer/import")
async def import_spammer_db(data: dict):
    spammers = data.get("spammers", [])
    with database.get_db() as conn:
        for s in spammers:
            conn.execute("""
                INSERT OR IGNORE INTO confirmed_spammers (user_id, reason, confirmed_at)
                VALUES (?, ?, ?)
            """, (s["user_id"], s.get("reason", ""), s.get("confirmed_at", datetime.now().isoformat())))
        conn.commit()
    return {"success": True, "imported": len(spammers)}

@app.post("/api/spammer/sync-cas")
async def sync_cas():
    # CAS sync via userbot
    from src import userbot as userbot_module
    added = 0
    # This is a placeholder - actual CAS sync would need implementation
    # For now, return success
    return {"success": True, "added": added}

# Serve static directory
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
def read_root():
    return {"status": "ClassicGuard Bot is running"}
