#!/usr/bin/env python3
"""
One-time script to authenticate userbot for OSINT checks.
Run this ONCE to create the session file, then you can delete this script.

In Docker:
    docker-compose run --rm app python auth_userbot.py
"""
import os
import sys
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()

API_ID = os.getenv("USERBOT_API_ID")
API_HASH = os.getenv("USERBOT_API_HASH")
SESSION = os.getenv("USERBOT_SESSION", "userbot_session")


async def main():
    if not API_ID or not API_HASH:
        print("❌ Error: USERBOT_API_ID and USERBOT_API_HASH must be set in .env")
        sys.exit(1)

    client = TelegramClient(SESSION, int(API_ID), API_HASH)
    
    print("🔐 Connecting to Telegram...")
    await client.connect()
    
    if not await client.is_user_authorized():
        print("📱 Please enter your phone number (with country code, e.g. +380...):")
        phone = input("> ").strip()
        
        await client.send_code_request(phone)
        print("📨 Enter the code you received:")
        code = input("> ").strip()
        
        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            print("🔒 Two-factor authentication enabled. Enter your password:")
            password = input("> ").strip()
            await client.sign_in(password=password)
    
    print("✅ Authorization successful!")
    print(f"💾 Session saved to: {SESSION}.session")
    print("\nYou can now use OSINT features. Keep this session file safe!")
    
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())