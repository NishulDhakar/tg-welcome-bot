"""
bot/database.py
───────────────
All Supabase interactions in one place.
Supabase Python client is synchronous; we run it in a thread executor
so it plays nicely with asyncio without blocking the event loop.
"""

import asyncio
import datetime
import functools
import logging
from typing import Any, Dict, List, Optional, Tuple

from supabase import create_client, Client

from bot.config import settings

logger = logging.getLogger(__name__)

# ── Client singleton ──────────────────────────────────────────────────────────
_client: Client = create_client(settings.supabase_url, settings.supabase_key)

# Table name – change here if you rename it in Supabase
TABLE = "users"


def _run_sync(func, *args, **kwargs):
    """Run a synchronous callable in a thread pool, returns a coroutine."""
    loop = asyncio.get_event_loop()
    bound = functools.partial(func, *args, **kwargs)
    return loop.run_in_executor(None, bound)


# ── Write ─────────────────────────────────────────────────────────────────────
async def save_user(
    telegram_id: int,
    username: Optional[str],
    first_name: Optional[str],
    last_name: Optional[str],
    source: str = "unknown",
) -> bool:
    """
    Upsert a user row.  Returns True on success, False on error.
    Upsert prevents duplicate rows if the user joins again.
    """
    payload: Dict[str, Any] = {
        "telegram_id": telegram_id,
        "username": username,
        "first_name": first_name,
        "last_name": last_name,
        "source": source,
        "status": "approved",
    }

    def _upsert():
        return _client.table(TABLE).upsert(payload, on_conflict="telegram_id").execute()

    try:
        await _run_sync(_upsert)
        logger.info("User %d saved/updated in DB.", telegram_id)
        return True
    except Exception as exc:
        logger.error("DB error saving user %d: %s", telegram_id, exc)
        return False


# ── Read ──────────────────────────────────────────────────────────────────────
async def get_all_users() -> List[Dict[str, Any]]:
    """Return all users with telegram_id, username, first_name."""

    def _fetch():
        return _client.table(TABLE).select("telegram_id, username, first_name").execute()

    try:
        result = await _run_sync(_fetch)
        logger.info("Fetched %d users from DB.", len(result.data))
        return result.data
    except Exception as exc:
        logger.error("DB error fetching users: %s", exc)
        return []


async def get_stats() -> Tuple[int, int]:
    """Return (total_users, joined_today)."""
    today_start = (
        datetime.datetime.now(datetime.timezone.utc)
        .replace(hour=0, minute=0, second=0, microsecond=0)
        .isoformat()
    )

    def _total():
        return _client.table(TABLE).select("id", count="exact").execute()

    def _today():
        return (
            _client.table(TABLE)
            .select("id", count="exact")
            .gte("joined_at", today_start)
            .execute()
        )

    try:
        total_res, today_res = await asyncio.gather(
            _run_sync(_total), _run_sync(_today)
        )
        total = total_res.count or 0
        today = today_res.count or 0
        logger.info("Stats → total=%d today=%d", total, today)
        return total, today
    except Exception as exc:
        logger.error("DB error fetching stats: %s", exc)
        return 0, 0
