"""
bot/handlers/admin.py
─────────────────────
Admin-only commands:
  /start      – welcome card with all available commands
  /stats      – total & today user counts
  /users      – paginated user list (up to 50)
  /broadcast  – send a DM to every registered user
  /addchannel – Add a new authorized channel
  /setmessage – Add a daily scheduled message to a channel
  /settime    – Set daily send time for a channel
  /listmessages – List all scheduled messages
  /removemessage – Remove a scheduled message
  /broadcastchannels – Broadcast a message to all admin channels
  /confirm    – Confirm a pending channel broadcast

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
        "/addchannel — Add a new authorized channel\n"
        "/setmessage `<channel_id> <message>` — Add a daily message\n"
        "/settime `<channel_id> <HH:MM>` — Set daily send time (UTC)\n"
        "/listmessages — List all scheduled messages\n"
        "/removemessage `<channel_id> <#>` — Remove a scheduled message\n"
        "/broadcastchannels `<message>` — Send to all admin channels\n"
        "/confirm — Confirm pending channel broadcast\n\n"
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


# ── /broadcastchannels ───────────────────────────────────────────────────
async def handle_broadcast_channels(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Preview a broadcast message and list target channels."""
    if not await _admin_only(update):
        return

    parts = update.message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await update.message.reply_text(
            "❌ Usage: /broadcastchannels <message>\n\n"
            "Example:\n/broadcastchannels Hello all channels!"
        )
        return

    message_text = parts[1].strip()

    # Gather all known channels (authorized + scheduled)
    all_channel_ids = set(settings.authorized_channels)
    for ch_id_str in settings.channel_schedules:
        try:
            all_channel_ids.add(int(ch_id_str))
        except ValueError:
            pass

    if not all_channel_ids:
        await update.message.reply_text(
            "ℹ️ No channels configured. Add channels with /addchannel first."
        )
        return

    await update.message.reply_text("🔍 Checking admin status in channels…")

    admin_channels = []
    for ch_id in all_channel_ids:
        try:
            member = await context.bot.get_chat_member(ch_id, context.bot.id)
            if member.status in ("administrator", "creator"):
                chat = await context.bot.get_chat(ch_id)
                admin_channels.append({"id": ch_id, "title": chat.title or str(ch_id)})
        except Exception as exc:
            logger.warning("Could not check channel %d: %s", ch_id, exc)

    if not admin_channels:
        await update.message.reply_text(
            "ℹ️ The bot is not an admin in any known channels."
        )
        return

    context.user_data["pending_broadcast_channels"] = message_text
    context.user_data["broadcast_channel_targets"] = admin_channels

    channel_list = "\n".join(
        f"  • {ch['title']} (`{ch['id']}`)" for ch in admin_channels
    )
    await update.message.reply_text(
        f"📢 *Broadcast Preview*\n\n"
        f"*Message:*\n{message_text}\n\n"
        f"*Will be sent to {len(admin_channels)} channel(s):*\n{channel_list}\n\n"
        f"Type /confirm to send or /cancel to abort.",
        parse_mode=constants.ParseMode.MARKDOWN,
    )
    logger.info(
        "Admin %d prepared channel broadcast to %d channels.",
        update.effective_user.id, len(admin_channels),
    )


# ── /confirm ──────────────────────────────────────────────────────────
async def handle_confirm(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Confirm and send a pending channel broadcast."""
    if not await _admin_only(update):
        return

    message_text = context.user_data.pop("pending_broadcast_channels", None)
    targets = context.user_data.pop("broadcast_channel_targets", None)

    if not message_text or not targets:
        await update.message.reply_text(
            "ℹ️ Nothing to confirm. Use /broadcastchannels first."
        )
        return

    status = await update.message.reply_text(
        f"🚀 Broadcasting to {len(targets)} channel(s)…"
    )

    delivered = 0
    failed = 0

    for ch in targets:
        try:
            await context.bot.send_message(chat_id=ch["id"], text=message_text)
            delivered += 1
        except Exception as exc:
            logger.warning("Channel broadcast failed → %s: %s", ch["id"], exc)
            failed += 1

    await status.edit_text(
        f"✅ Channel broadcast complete!\n\n"
        f"📨 Delivered: {delivered}\n"
        f"❌ Failed: {failed}"
    )
    logger.info(
        "Channel broadcast by admin %d → delivered=%d failed=%d",
        update.effective_user.id, delivered, failed,
    )


# ── /cancel ───────────────────────────────────────────────────────────
async def handle_cancel(
    update: Update, context: ContextTypes.DEFAULT_TYPE
) -> None:
    """Cancel any pending operation."""
    if not await _admin_only(update):
        return

    cleared = False
    if context.user_data.pop("pending_broadcast_channels", None):
        context.user_data.pop("broadcast_channel_targets", None)
        cleared = True
    if context.user_data.pop("awaiting_channel_id", None):
        cleared = True

    if cleared:
        await update.message.reply_text("✅ Operation cancelled.")
    else:
        await update.message.reply_text("ℹ️ Nothing to cancel.")


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
