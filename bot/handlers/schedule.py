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

from telegram import Update, constants
from telegram.ext import Application, ContextTypes

from bot.config import settings

logger = logging.getLogger(__name__)


# ── Guard ─────────────────────────────────────────────────────────────────────
async def _admin_only(update: Update) -> bool:
    uid = update.effective_user.id
    if settings.is_admin(uid):
        return True
    logger.warning("Non-admin %d tried an admin command.", uid)
    return False


# ── /setmessage ───────────────────────────────────────────────────────────────
async def handle_setmessage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Add a scheduled daily message for a channel."""
    if not await _admin_only(update):
        return

    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Usage: /setmessage <channel_id> <message>\n\n"
            "Example:\n/setmessage -1001234567890 Good morning everyone!"
        )
        return

    try:
        channel_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
        return

    message_text = parts[2].strip()
    settings.add_scheduled_message(channel_id, message_text)

    schedule = settings.channel_schedules.get(str(channel_id), {})
    time_str = schedule.get("time")

    if time_str:
        await update.message.reply_text(
            f"✅ Message added to channel `{channel_id}`\n"
            f"⏰ Daily send time: {time_str} UTC\n"
            f"📝 Message: {message_text}",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    else:
        await update.message.reply_text(
            f"✅ Message added to channel `{channel_id}`\n\n"
            f"⚠️ No send time set yet! Use:\n"
            f"/settime {channel_id} HH:MM",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
    logger.info("Admin %d added scheduled message for channel %d.", update.effective_user.id, channel_id)


# ── /settime ──────────────────────────────────────────────────────────────────
async def handle_settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Set/update the daily send time for a channel (UTC)."""
    if not await _admin_only(update):
        return

    parts = update.message.text.split(maxsplit=2)
    if len(parts) < 3:
        await update.message.reply_text(
            "❌ Usage: /settime <channel_id> <HH:MM>\n\n"
            "Example:\n/settime -1001234567890 09:00"
        )
        return

    try:
        channel_id = int(parts[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid channel ID. Must be a number.")
        return

    time_str = parts[2].strip()
    try:
        hour, minute = map(int, time_str.split(":"))
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
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
        f"⏰ Time: {time_str} UTC\n"
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
        lines.append(f"📢 Channel: `{ch_id}` | ⏰ {time_str} UTC")
        for i, msg in enumerate(messages, 1):
            preview = msg[:60] + "…" if len(msg) > 60 else msg
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
        time=datetime.time(hour=hour, minute=minute, tzinfo=datetime.timezone.utc),
        data=channel_id,
        name=job_name,
    )
    logger.info("Scheduled daily job for channel %d at %02d:%02d UTC.", channel_id, hour, minute)


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
            await context.bot.send_message(chat_id=channel_id, text=msg)
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
                time=datetime.time(hour=hour, minute=minute, tzinfo=datetime.timezone.utc),
                data=channel_id,
                name=f"schedule_{channel_id}",
            )
            logger.info("Restored schedule for channel %d at %s UTC.", channel_id, time_str)
        except Exception as exc:
            logger.error("Failed to restore schedule for channel %s: %s", ch_id_str, exc)
