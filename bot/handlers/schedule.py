"""
bot/handlers/schedule.py
────────────────────────
Scheduled daily messages:
  /setmessage   – Add a daily message to a channel
  /settime      – Set the daily send time for a channel (UTC)
  /listmessages – List all scheduled messages
  /removemessage – Remove a scheduled message
"""

import datetime
import logging
import re
from zoneinfo import ZoneInfo

from telegram import Update, constants
from telegram.ext import Application, ContextTypes

from bot.config import settings

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")
_PUBLIC_POST_RE = re.compile(
    r"^https?://t\.me/(?P<username>[A-Za-z0-9_]+)/(?P<message_id>\d+)(?:\?.*)?$"
)
_PRIVATE_POST_RE = re.compile(
    r"^https?://t\.me/c/(?P<chat_id>\d+)/(?P<message_id>\d+)(?:\?.*)?$"
)


# ── Guard ─────────────────────────────────────────────────────────────────────
async def _admin_only(update: Update) -> bool:
    uid = update.effective_user.id
    if settings.is_admin(uid):
        return True
    logger.warning("Non-admin %d tried an admin command.", uid)
    return False


def _parse_time_ist(time_str: str) -> tuple[int, int]:
    hour, minute = map(int, time_str.split(":"))
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError
    return hour, minute


def _parse_post_link(post_link: str) -> tuple[int | str, int]:
    public_match = _PUBLIC_POST_RE.match(post_link)
    if public_match:
        source_chat_id = f"@{public_match.group('username')}"
        return source_chat_id, int(public_match.group("message_id"))

    private_match = _PRIVATE_POST_RE.match(post_link)
    if private_match:
        source_chat_id = int(f"-100{private_match.group('chat_id')}")
        return source_chat_id, int(private_match.group("message_id"))

    raise ValueError("Unsupported Telegram post link format")


def _preview_message(message: str | dict) -> str:
    if isinstance(message, dict) and message.get("kind") == "copy":
        return f"copy {message.get('source_link', 'telegram post')}"

    text = str(message)
    return text[:60] + "…" if len(text) > 60 else text


def _looks_like_post_schedule(parts: list[str]) -> bool:
    return len(parts) == 4 and parts[2].startswith(("http://", "https://"))


# ── /setmessage ───────────────────────────────────────────────────────────────
async def handle_setmessage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a scheduled daily message or copied post for a channel."""
    if not await _admin_only(update):
        return

    parts = update.message.text.split(maxsplit=3)
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Usage:\n"
            "/setmessage <channel_id> <post_link> <HH:MM>\n"
            "/setmessage <channel_id> <message>\n\n"
            "Examples:\n"
            "/setmessage -1001234567890 https://t.me/channelname/15 09:30\n"
            "/setmessage -1001234567890 Good morning everyone!"
        )
        return

    try:
        channel_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
        return

    if len(parts) == 4:
        post_link = parts[2].strip()
        time_str = parts[3].strip()
        try:
            source_chat_id, message_id = _parse_post_link(post_link)
            hour, minute = _parse_time_ist(time_str)
        except ValueError:
            if _looks_like_post_schedule(parts):
                await update.message.reply_text(
                    "❌ Invalid Telegram post link or time.\n\n"
                    "Example:\n"
                    "/setmessage -1001234567890 https://t.me/channelname/15 09:30\n\n"
                    "Time is interpreted in Asia/Kolkata.",
                )
                return
        else:
            settings.add_scheduled_copy_message(channel_id, source_chat_id, message_id, post_link)
            settings.set_schedule_time(channel_id, time_str)
            _schedule_channel_job(context, channel_id, hour, minute)

            await update.message.reply_text(
                f"✅ Daily copied post scheduled for channel `{channel_id}`\n"
                f"🔗 Source: {post_link}\n"
                f"⏰ Time: {time_str} IST\n\n"
                "The bot will copy the post, so the sender name stays hidden.",
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            logger.info(
                "Admin %d added scheduled copied post for channel %d from %s.",
                update.effective_user.id,
                channel_id,
                post_link,
            )
            return

    message_text = update.message.text.split(maxsplit=2)[2].strip()
    settings.add_scheduled_message(channel_id, message_text)

    schedule = settings.channel_schedules.get(str(channel_id), {})
    time_str = schedule.get("time")

    if time_str:
        await update.message.reply_text(
            f"✅ Message added to channel `{channel_id}`\n"
            f"⏰ Daily send time: {time_str} IST\n"
            f"📝 Message: {message_text}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            f"✅ Message added to channel `{channel_id}`\n\n"
            f"⚠️ No send time set yet. Use:\n"
            f"/settime {channel_id} HH:MM\n\n"
            "Time is interpreted in Asia/Kolkata.",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    logger.info("Admin %d added scheduled message for channel %d.", update.effective_user.id, channel_id)


# ── /settime ──────────────────────────────────────────────────────────────────
async def handle_settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set/update the daily send time for a channel (Asia/Kolkata)."""
    if not await _admin_only(update):
        return

    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Usage: /settime <channel_id> <HH:MM>\n\n"
            "Example:\n/settime -1001234567890 09:00\n\n"
            "Time is interpreted in Asia/Kolkata."
        )
        return

    try:
        channel_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
        return

    time_str = parts[2].strip()
    try:
        hour, minute = _parse_time_ist(time_str)
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid time format. Use HH:MM (24h), e.g. 09:00 or 18:30"
        )
        return

    settings.set_schedule_time(channel_id, time_str)

    # Reschedule the job
    _schedule_channel_job(context, channel_id, hour, minute)

    schedule = settings.channel_schedules.get(str(channel_id), {})
    msg_count = len(schedule.get("messages", []))

    await update.message.reply_text(
        f"✅ Daily send time set for channel `{channel_id}`\n"
        f"⏰ Time: {time_str} IST\n"
        f"📝 Messages scheduled: {msg_count}",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    logger.info("Admin %d set schedule time %s for channel %d.", update.effective_user.id, time_str, channel_id)


# ── /listmessages ─────────────────────────────────────────────────────────────
async def handle_listmessages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List all scheduled messages across all channels."""
    if not await _admin_only(update):
        return

    schedules = settings.channel_schedules
    if not schedules:
        await update.message.reply_text("ℹ️ No scheduled messages configured.")
        return

    lines = ["📋 *Scheduled Messages*\n"]
    for ch_id, data in schedules.items():
        time_str = data.get("time") or "Not set"
        messages = data.get("messages", [])
        lines.append(f"📢 Channel: `{ch_id}` | ⏰ {time_str} IST")
        for i, msg in enumerate(messages, 1):
            preview = _preview_message(msg)
            lines.append(f"  {i}. {preview}")
        lines.append("")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=constants.ParseMode.MARKDOWN,
    )


# ── /removemessage ────────────────────────────────────────────────────────────
async def handle_removemessage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Remove a scheduled message by channel ID and message number."""
    if not await _admin_only(update):
        return

    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Usage: /removemessage <channel_id> <number>\n\n"
            "Use /listmessages to see message numbers."
        )
        return

    try:
        channel_id = int(parts[1])
        msg_index = int(parts[2]) - 1  # Convert to 0-based
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID or message number.")
        return

    removed = settings.remove_scheduled_message(channel_id, msg_index)
    if removed:
        # If no messages left for this channel, cancel the job
        schedule = settings.channel_schedules.get(str(channel_id))
        if not schedule:
            _cancel_channel_job(context, channel_id)

        await update.message.reply_text(
            f"✅ Message removed from channel `{channel_id}`",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        logger.info("Admin %d removed scheduled message from channel %d.", update.effective_user.id, channel_id)
    else:
        await update.message.reply_text(
            "❌ Could not find that message. Use /listmessages to check."
        )


# ── Scheduler helpers ─────────────────────────────────────────────────────────
def _schedule_channel_job(context: ContextTypes.DEFAULT_TYPE, channel_id: int, hour: int, minute: int) -> None:
    """Create or replace a daily job for a channel."""
    job_name = f"schedule_{channel_id}"

    # Remove existing job if any
    _cancel_channel_job(context, channel_id)

    context.job_queue.run_daily(
        _send_scheduled_messages,
        time=datetime.time(hour=hour, minute=minute, tzinfo=IST),
        data=channel_id,
        name=job_name,
    )
    logger.info("Scheduled daily job for channel %d at %02d:%02d IST.", channel_id, hour, minute)


def _cancel_channel_job(context: ContextTypes.DEFAULT_TYPE, channel_id: int) -> None:
    """Cancel the daily job for a channel."""
    job_name = f"schedule_{channel_id}"
    current_jobs = context.job_queue.get_jobs_by_name(job_name)
    for job in current_jobs:
        job.schedule_removal()
    if current_jobs:
        logger.info("Cancelled scheduled job for channel %d.", channel_id)


async def _send_scheduled_messages(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Job callback: send all scheduled messages for a channel."""
    channel_id = context.job.data
    schedule = settings.channel_schedules.get(str(channel_id), {})
    messages = schedule.get("messages", [])

    for msg in messages:
        try:
            if isinstance(msg, dict) and msg.get("kind") == "copy":
                await context.bot.copy_message(
                    chat_id=channel_id,
                    from_chat_id=msg["source_chat_id"],
                    message_id=msg["message_id"],
                )
                logger.info(
                    "Scheduled copied post sent to channel %d from %s.",
                    channel_id,
                    msg.get("source_chat_id"),
                )
            else:
                await context.bot.send_message(chat_id=channel_id, text=str(msg))
                logger.info("Scheduled message sent to channel %d.", channel_id)
        except Exception as exc:
            logger.error("Failed to send scheduled message to channel %d: %s", channel_id, exc)


# ── Startup initializer ──────────────────────────────────────────────────────
def initialize_schedules(app: Application) -> None:
    """Called on startup to restore daily jobs from saved config."""
    for ch_id_str, data in settings.channel_schedules.items():
        time_str = data.get("time")
        messages = data.get("messages", [])
        if not time_str or not messages:
            continue

        try:
            hour, minute = map(int, time_str.split(":"))
            channel_id = int(ch_id_str)
            app.job_queue.run_daily(
                _send_scheduled_messages,
                time=datetime.time(hour=hour, minute=minute, tzinfo=IST),
                data=channel_id,
                name=f"schedule_{channel_id}",
            )
            logger.info("Restored schedule for channel %d at %s IST.", channel_id, time_str)
        except Exception as exc:
            logger.error("Failed to restore schedule for channel %s: %s", ch_id_str, exc)
