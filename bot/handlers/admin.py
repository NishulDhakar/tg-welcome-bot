"""
bot/handlers/admin.py
─────────────────────
Admin-only commands:
  /start     – welcome card with all available commands
  /stats     – total & today user counts
  /users     – paginated user list (up to 50)
  /broadcast – send a DM to every registered user
  /addchannel – Add a new authorized channel

Only Telegram IDs listed in ADMIN_IDS (.env) can use these commands.
"""

import asyncio
import logging

from telegram import Update, constants
from telegram.ext import ContextTypes

from bot.config import settings
from bot.database import get_all_users, get_stats
from bot.messages import stats as stats_msg, user_list as user_list_msg, broadcast_body

logger = logging.getLogger(__name__)

# Delay between messages during broadcast to respect Telegram rate limits
_BROADCAST_DELAY = 0.05  # 50 ms → ~20 msg/s  (well within 30/s limit)


# ── Guard decorator ───────────────────────────────────────────────────────────
async def _admin_only(update: Update) -> bool:
    """Return True if the sender is an admin; silently ignore otherwise."""
    uid = update.effective_user.id
    if settings.is_admin(uid):
        return True
    logger.warning("Non-admin %d tried an admin command.", uid)
    return False


# ── /start ───────────────────────────────────────────────────────────────────
async def handle_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a help card listing all admin commands."""
    if not await _admin_only(update):
        return

    name = update.effective_user.first_name or "Admin"
    text = (
        f"👋 Hey {name}! Here are your admin commands:\n\n"
        "/stats — Total users & today's joins\n"
        "/users — List registered users (up to 50)\n"
        "/broadcast `<message>` — DM everyone in the DB\n"
        "/addchannel — Add a new authorized channel\n\n"
        "_Type / to see command suggestions at any time._"
    )
    await update.message.reply_text(text, parse_mode=constants.ParseMode.MARKDOWN)
    logger.info("Start/help sent to admin %d.", update.effective_user.id)


# ── /stats ────────────────────────────────────────────────────────────────────
async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return

    total, today = await get_stats()
    await update.message.reply_text(
        stats_msg(total, today),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    logger.info("Stats sent to admin %d.", update.effective_user.id)


# ── /users ────────────────────────────────────────────────────────────────────
async def handle_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return

    users = await get_all_users()
    await update.message.reply_text(
        user_list_msg(users),
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    logger.info(
        "User list (%d entries) sent to admin %d.",
        len(users), update.effective_user.id,
    )


# ── /broadcast ────────────────────────────────────────────────────────────────
async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _admin_only(update):
        return

    # Parse message text after the command word
    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "❌ Usage: /broadcast <message>\n\nExample:\n/broadcast Hello everyone!"
        )
        return

    text = broadcast_body(parts[1].strip())
    users = await get_all_users()

    if not users:
        await update.message.reply_text("ℹ️ No users in the database yet.")
        return

    status = await update.message.reply_text(
        f"🚀 Broadcasting to {len(users)} users…"
    )

    delivered = 0
    failed    = 0

    for user in users:
        try:
            await context.bot.send_message(
                chat_id=user["telegram_id"],
                text=text,
                parse_mode=constants.ParseMode.MARKDOWN,
            )
            delivered += 1
        except Exception as exc:
            logger.warning(
                "Broadcast failed → user %s: %s",
                user.get("telegram_id"), exc,
            )
            failed += 1
        finally:
            # Small sleep to avoid hitting Telegram rate limits
            await asyncio.sleep(_BROADCAST_DELAY)

    await status.edit_text(
        f"✅ Broadcast complete!\n\n"
        f"📨 Delivered: {delivered}\n"
        f"❌ Failed:    {failed}"
    )
    logger.info(
        "Broadcast by admin %d → delivered=%d failed=%d",
        update.effective_user.id, delivered, failed,
    )

# ── /addchannel ───────────────────────────────────────────────────────────────
async def handle_add_channel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Start the process of adding a new authorized channel."""
    if not await _admin_only(update):
        return

    # Check if ID was provided as an argument
    parts = update.message.text.split(maxsplit=1)
    if len(parts) > 1:
        await _process_channel_id(update, context, parts[1].strip())
        return

    # No ID provided → ask for it
    context.user_data["awaiting_channel_id"] = True
    await update.message.reply_text(
        "📝 Please send me the **Channel ID** you want to authorize.\n\n"
        "Example: `-1001234567890`",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def handle_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages from admins (e.g. for /addchannel state)."""
    if not await _admin_only(update):
        return

    if context.user_data.get("awaiting_channel_id"):
        await _process_channel_id(update, context, update.message.text.strip())
        return


async def _process_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE, raw_id: str) -> None:
    """Helper to validate and save a channel ID."""
    try:
        channel_id = int(raw_id)
        settings.add_channel(channel_id)
        
        context.user_data["awaiting_channel_id"] = False
        await update.message.reply_text(
            f"✅ **Channel Authorized!**\n\n"
            f"ID: `{channel_id}`\n"
            f"The bot will now process join requests for this channel.",
            parse_mode=constants.ParseMode.MARKDOWN,
        )
        logger.info("Admin %d added channel %d.", update.effective_user.id, channel_id)
    except ValueError:
        await update.message.reply_text(
            "❌ Invalid ID. Please send a numeric ID (e.g., `-100...`).\n"
            "Try again or type /start to cancel."
        )
