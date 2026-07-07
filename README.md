# 🛡️ ClassicGuard — Telegram Captcha Bot

> A advanced captcha-guard administration bot to protect Telegram groups against spam bots, utilizing FastAPI, userbots, and WebApp verifications.

## 🚀 Features

- **FastAPI Webhook Handler**: High-speed processing of Telegram updates.
- **Multitier Verification System**:
  - **Device / IP / Fingerprint checks** to detect multi-account setups and spoofed environments.
  - **Avatar & Premium status verification**: Identifies blank spam accounts.
  - **Account Age restriction**: Automatically filters accounts created less than $N$ months ago.
- **Integration with Global Blacklists**:
  - **CAS (Combot Anti-Spam)** validation.
  - Custom OSINT check pipelines.
- **Interactive WebApp Captcha**: Dynamic questions rendered inside WebApp overlays to challenge incoming members.
- **Anti-Twink Detection**: Declines known spam setups before they message the group.
- **Flexible Settings**: Customized moderation rules per group, managed directly through dashboard structures.

## 🛠️ Tech Stack

- **Language**: Python 3.10+
- **Backend Framework**: `FastAPI` (ASGI web framework)
- **Telegram APIs**: Direct HTTP requests (`bot_api`), custom integration handlers, and Pyrogram Userbot capabilities (`userbot_module`).
- **Database**: SQLite (local config storage)
- **Deployment**: Docker / Docker Compose

## 📁 Project Structure

```
ClassicGuard/
├── src/
│   ├── config.py         # App configuration & environment settings
│   ├── database.py       # Group moderation settings storage (SQLite)
│   ├── bot_api.py        # Custom API request wrapper for Telegram bots
│   ├── userbot.py        # Client userbot integrations (spam analysis)
│   ├── main.py           # FastAPI entry point, webhooks, and verification endpoints
│   └── templates/        # WebApp frontend templates (Captcha interfaces)
├── auth_userbot.py       # Helper script to authorize the userbot client
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env
```

## ⚙️ Configuration & Run

### 1. Environment Settings
Create a `.env` file in the root directory:
```env
BOT_TOKEN=your_telegram_bot_token
WEBAPP_URL=https://your-public-domain-or-ngrok.com
API_ID=your_telegram_api_id
API_HASH=your_telegram_api_hash
```

### 2. Userbot Authentication (Optional)
Run the script to create a session:
```bash
python auth_userbot.py
```

### 3. Deploy with Docker
```bash
docker compose up -d
```

---
*Developed by Mykhailo Chernykh.*
