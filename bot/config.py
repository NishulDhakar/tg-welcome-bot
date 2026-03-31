"""
bot/config.py
─────────────
Single source of truth for all environment-based settings.
Raises EnvironmentError on startup if required vars are missing.
"""

import os
import json
import logging
from dataclasses import dataclass, field
from typing import List, Set

from dotenv import load_dotenv

load_dotenv()

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ── Config File Path ─────────────────────────────────────────────────────────
CONFIG_FILE = "config.json"

# ── Settings dataclass ────────────────────────────────────────────────────────
@dataclass
class Settings:
    bot_token: str
    supabase_url: str
    supabase_key: str
    admin_ids: List[int] = field(default_factory=list)
    welcome_message: str = "Hey {first_name}! Welcome! 🎉"
    authorized_channels: Set[int] = field(default_factory=set)

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids

    def is_channel_authorized(self, chat_id: int) -> bool:
        return chat_id in self.authorized_channels

    def add_channel(self, chat_id: int) -> None:
        if chat_id not in self.authorized_channels:
            self.authorized_channels.add(chat_id)
            self._save_dynamic_config()

    def remove_channel(self, chat_id: int) -> None:
        if chat_id in self.authorized_channels:
            self.authorized_channels.remove(chat_id)
            self._save_dynamic_config()

    def _save_dynamic_config(self) -> None:
        """Persist dynamic settings to JSON."""
        data = {
            "authorized_channels": list(self.authorized_channels)
        }
        try:
            with open(CONFIG_FILE, "w") as f:
                json.dump(data, f, indent=4)
            logger.info("Dynamic config saved to %s", CONFIG_FILE)
        except Exception as exc:
            logger.error("Failed to save dynamic config: %s", exc)


def _load_dynamic_config() -> dict:
    """Load dynamic settings from JSON if they exist."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception as exc:
            logger.warning("Failed to load dynamic config from %s: %s", CONFIG_FILE, exc)
    return {}


def _load_settings() -> Settings:
    missing: List[str] = []

    bot_token    = os.getenv("BOT_TOKEN", "").strip()
    supabase_url = os.getenv("SUPABASE_URL", "").strip()
    supabase_key = os.getenv("SUPABASE_KEY", "").strip()
    
    # CHANNEL_ID from env is now optional (legacy support)
    raw_channel_id = os.getenv("CHANNEL_ID", "").strip()

    for name, val in [
        ("BOT_TOKEN", bot_token),
        ("SUPABASE_URL", supabase_url),
        ("SUPABASE_KEY", supabase_key),
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

    # Load dynamic config
    dynamic_config = _load_dynamic_config()
    authorized_channels = set(dynamic_config.get("authorized_channels", []))

    # Incorporate legacy CHANNEL_ID if present
    if raw_channel_id:
        try:
            authorized_channels.add(int(raw_channel_id))
        except ValueError:
            logger.warning("Legacy CHANNEL_ID in .env is not a valid integer: %s", raw_channel_id)

    settings = Settings(
        bot_token=bot_token,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        admin_ids=admin_ids,
        welcome_message=welcome_message,
        authorized_channels=authorized_channels,
    )

    logger.info(
        "Config loaded. Admins: %s | Authorized Channels: %s",
        settings.admin_ids,
        list(settings.authorized_channels),
    )
    return settings


# Module-level singleton – imported everywhere as `from bot.config import settings`
settings: Settings = _load_settings()
