"""
OSINT userbot via Telethon (MTProto).
Collects hidden profile metadata: registration month, country, scam flags.
"""
import os
import asyncio
import logging
from telethon import TelegramClient, functions, types
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from typing import Optional, Dict, Any
import time

logger = logging.getLogger(__name__)

# In-memory cache: user_id -> osint_result
osint_cache: Dict[int, Dict[str, Any]] = {}
CACHE_TTL = 60 * 60 * 24  # 24 hours

_client: Optional[TelegramClient] = None
_client_lock = asyncio.Lock()


def _get_api_credentials():
    api_id = os.getenv("USERBOT_API_ID", "")
    api_hash = os.getenv("USERBOT_API_HASH", "")
    session_file = os.getenv("USERBOT_SESSION", "userbot_session")
    return api_id, api_hash, session_file


async def get_client() -> Optional[TelegramClient]:
    global _client
    if _client is not None and _client.is_connected():
        return _client

    api_id, api_hash, session_file = _get_api_credentials()
    if not api_id or not api_hash:
        logger.warning("USERBOT_API_ID / USERBOT_API_HASH not set. OSINT disabled.")
        return None

    async with _client_lock:
        if _client is not None and _client.is_connected():
            return _client
        try:
            _client = TelegramClient(session_file, int(api_id), api_hash)
            await _client.connect()
            if not await _client.is_user_authorized():
                logger.warning("Userbot session not authorized. Run auth script first.")
                await _client.disconnect()
                _client = None
                return None
            logger.info("Userbot client connected.")
            return _client
        except Exception as e:
            logger.error(f"Userbot connection error: {e}")
            _client = None
            return None


async def close_client():
    global _client
    if _client and _client.is_connected():
        await _client.disconnect()
        _client = None


async def osint_lookup(user_id: int) -> Dict[str, Any]:
    """
    Returns dict with:
      - is_scam: bool
      - is_fake: bool
      - avatar_count: int
      - avatar_dates: list of unix timestamps (most recent first)
      - avatar_spam_score: int (higher = more suspicious)
    """
    now = time.time()
    cached = osint_cache.get(user_id)
    if cached and (now - cached.get("ts", 0)) < CACHE_TTL:
        return cached.get("data", {})

    client = await get_client()
    if client is None:
        return {"error": "userbot_not_available"}

    try:
        # Resolve user by ID or username
        try:
            entity = await client.get_entity(user_id)
        except ValueError:
            # If direct get_entity fails, try via GetFullUserRequest with InputUser
            # We need access_hash, so try to find via dialogs or contacts
            # Fallback: return limited info
            return {"error": "user_not_found", "user_id": user_id}

        result = await client(functions.users.GetFullUserRequest(
            user_id=entity
        ))

        user = result.users[0] if result.users else None
        full = result.full_user

        info: Dict[str, Any] = {
            "user_id": user_id,
            "is_scam": bool(user and getattr(user, "scam", False)),
            "is_fake": bool(user and getattr(user, "fake", False)),
            "avatar_count": 0,
            "avatar_dates": [],
            "avatar_spam_score": 0,
        }

        # Fetch avatar photos with dates via MTProto
        try:
            photos_result = await client(functions.photos.GetUserPhotosRequest(
                user_id=entity,
                offset=0,
                max_id=0,
                limit=50  # up to 50 avatars
            ))
            photos = photos_result.photos if photos_result else []
            info["avatar_count"] = len(photos)

            avatar_dates = []
            for photo in photos:
                # photo.date is unix timestamp
                d = getattr(photo, "date", None)
                if d:
                    avatar_dates.append(int(d))
            avatar_dates.sort(reverse=True)  # newest first
            info["avatar_dates"] = avatar_dates

            # Calculate spam score:
            # +2 if all avatars uploaded within 1 hour (batch upload)
            # +3 if all avatars uploaded within 24 hours
            # +1 if more than 5 avatars
            # +2 if more than 10 avatars
            score = 0
            if len(avatar_dates) >= 2:
                span_seconds = avatar_dates[0] - avatar_dates[-1]
                span_hours = span_seconds / 3600
                if span_hours <= 1:
                    score += 2
                if span_hours <= 24:
                    score += 3
            if len(avatar_dates) > 5:
                score += 1
            if len(avatar_dates) > 10:
                score += 2
            info["avatar_spam_score"] = score

        except Exception as e:
            logger.warning(f"Failed to fetch avatar photos for {user_id}: {e}")
            # Non-critical, continue without avatar data

        osint_cache[user_id] = {"ts": now, "data": info}
        return info

    except FloodWaitError as e:
        logger.warning(f"OSINT flood wait: {e}")
        return {"error": "flood_wait", "wait_seconds": getattr(e, "seconds", 60)}
    except Exception as e:
        logger.error(f"OSINT lookup error for {user_id}: {e}")
        return {"error": str(e)}


def clear_cache():
    osint_cache.clear()