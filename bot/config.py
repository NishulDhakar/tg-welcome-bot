"""
bot/config.py
─────────────
Single source of truth for all environment-based settings.
Raises EnvironmentError on startup if required vars are missing.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ── Settings dataclass ────────────────────────────────────────────────────────
@dataclass(frozen=True)
class Settings:
    bot_token: str
    supabase_url: str
    supabase_key: str
    channel_id: str
    admin_ids: List[int] = field(default_factory=list)
    welcome_message: str = "Hey {first_name}! Welcome! 🎉"

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


def _require(name: str) -> str:
    """Return env var or raise a clear error."""
    value = os.getenv(name, "").strip()
    if not value:
        raise EnvironmentError(
            f"Required environment variable '{name}' is missing or empty. "
            "Check your .env file."
        )
    return value


def _load_settings() -> Settings:
    missing: List[str] = []

    bot_token    = os.getenv("BOT_TOKEN", "").strip()
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()
    channel_id   = os.getenv("CHANNEL_ID", "").strip()

    for name, val in [
        ("BOT_TOKEN", bot_token),
        ("SUPABASE_URL", supabase_url),
        ("SUPABASE_KEY", supabase_key),
        ("CHANNEL_ID", channel_id),
    ]:
        if not val:
            missing.append(name)

    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}. "
            "Check your .env file."
        )

    # Parse ADMIN_IDS – comma-separated integers
    admin_ids: List[int] = []
    raw_ids = os.getenv("ADMIN_IDS", "")
    for part in raw_ids.split(","):
        part = part.strip()
        if part:
            try:
                admin_ids.append(int(part))
            except ValueError:
                logger.warning("Skipping non-integer ADMIN_ID value: %r", part)

    welcome_message = os.getenv(
        "WELCOME_MESSAGE", "Hey {first_name}! Welcome! 🎉"
    )

    settings = Settings(
        bot_token=bot_token,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        channel_id=channel_id,
        admin_ids=admin_ids,
        welcome_message=welcome_message,
    )

    logger.info(
        "Config loaded. Admins: %s | Channel: %s",
        settings.admin_ids,
        settings.channel_id,
    )
    return settings


# Module-level singleton – imported everywhere as `from bot.config import settings`
settings: Settings = _load_settings()
