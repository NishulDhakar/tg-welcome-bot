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
from typing import Any, Dict, List, Optional, Set

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
    welcome_button_text: Optional[str] = None
    welcome_button_url: Optional[str] = None
    authorized_channels: Set[int] = field(default_factory=set)
    channel_schedules: Dict[str, Dict[str, Any]] = field(default_factory=dict)

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

    def set_welcome_message(self, message: str) -> None:
        self.welcome_message = message
        self._save_dynamic_config()

    def set_welcome_button(self, text: Optional[str], url: Optional[str]) -> None:
        self.welcome_button_text = text or None
        self.welcome_button_url = url or None
        self._save_dynamic_config()

    # ── Scheduled messages ────────────────────────────────────────────────────
    def add_scheduled_message(self, channel_id: int, message: str) -> None:
        key = str(channel_id)
        if key not in self.channel_schedules:
            self.channel_schedules[key] = {"time": None, "messages": []}
        self.channel_schedules[key]["messages"].append(message)
        self._save_dynamic_config()

    def add_scheduled_copy_message(
        self,
        channel_id: int,
        source_chat_id: Any,
        message_id: int,
        source_link: str,
    ) -> None:
        key = str(channel_id)
        if key not in self.channel_schedules:
            self.channel_schedules[key] = {"time": None, "messages": []}

        self.channel_schedules[key]["messages"].append(
            {
                "kind": "copy",
                "source_chat_id": source_chat_id,
                "message_id": message_id,
                "source_link": source_link,
            }
        )
        self._save_dynamic_config()

    def remove_scheduled_message(self, channel_id: int, index: int) -> bool:
        key = str(channel_id)
        schedule = self.channel_schedules.get(key)
        if not schedule or index < 0 or index >= len(schedule.get("messages", [])):
            return False
        schedule["messages"].pop(index)
        if not schedule["messages"]:
            del self.channel_schedules[key]
        self._save_dynamic_config()
        return True

    def set_schedule_time(self, channel_id: int, time_str: str) -> None:
        key = str(channel_id)
        if key not in self.channel_schedules:
            self.channel_schedules[key] = {"time": time_str, "messages": []}
        else:
            self.channel_schedules[key]["time"] = time_str
        self._save_dynamic_config()

    def _save_dynamic_config(self) -> None:
        """Persist dynamic settings to JSON."""
        data = {
            "welcome": {
                "message": self.welcome_message,
                "button_text": self.welcome_button_text,
                "button_url": self.welcome_button_url,
            },
            "authorized_channels": list(self.authorized_channels),
            "channel_schedules": self.channel_schedules,
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
    welcome_button_text = os.getenv("WELCOME_BUTTON_TEXT", "").strip() or None
    welcome_button_url = os.getenv("WELCOME_BUTTON_URL", "").strip() or None

    # Load dynamic config
    dynamic_config = _load_dynamic_config()
    welcome_config = dynamic_config.get("welcome", {})
    authorized_channels = set(dynamic_config.get("authorized_channels", []))
    channel_schedules = dynamic_config.get("channel_schedules", {})

    if "message" in welcome_config and welcome_config.get("message"):
        welcome_message = welcome_config["message"]
    if "button_text" in welcome_config:
        welcome_button_text = welcome_config.get("button_text") or None
    if "button_url" in welcome_config:
        welcome_button_url = welcome_config.get("button_url") or None

    settings = Settings(
        bot_token=bot_token,
        supabase_url=supabase_url,
        supabase_key=supabase_key,
        admin_ids=admin_ids,
        welcome_message=welcome_message,
        welcome_button_text=welcome_button_text,
        welcome_button_url=welcome_button_url,
        authorized_channels=authorized_channels,
        channel_schedules=channel_schedules,
    )

    logger.info(
        "Config loaded. Admins: %s | Authorized Channels: %s",
        settings.admin_ids,
        list(settings.authorized_channels),
    )
    return settings


# Module-level singleton – imported everywhere as `from bot.config import settings`
settings: Settings = _load_settings()
