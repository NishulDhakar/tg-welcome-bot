"""
bot.py
──────
Entry point.  Run with:  python bot.py

Commands are registered per-admin via BotCommandScopeChat so they
appear in the "/" suggestion list only for admin users.
"""

import asyncio
import logging

from telegram import BotCommand, BotCommandScopeChat
from telegram.ext import (
    Application,
    ChatJoinRequestHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import settings
from bot.handlers.admin import (
    handle_add_channel,
    handle_admin_message,
    handle_broadcast,
    handle_broadcast_channels,
    handle_cancel,
    handle_confirm,
    handle_setwelcome,
    handle_start,
    handle_stats,
    handle_users,
)
from bot.handlers.join import handle_join_request
from bot.handlers.schedule import (
    handle_listmessages,
    handle_removemessage,
    handle_setmessage,
    handle_settime,
    initialize_schedules,
)

logger = logging.getLogger(__name__)

# Commands shown only to admins when they type "/"
_ADMIN_COMMANDS = [
    BotCommand("start",             "Show all available commands"),
    BotCommand("stats",             "User statistics"),
    BotCommand("users",             "List registered users"),
    BotCommand("broadcast",         "Send a message to all users"),
    BotCommand("addchannel",        "Add an authorized channel"),
    BotCommand("setmessage",        "Schedule a copied post or daily text"),
    BotCommand("settime",           "Set daily send time in IST"),
    BotCommand("setwelcome",        "Customize welcome message and button"),
    BotCommand("listmessages",      "List all scheduled messages"),
    BotCommand("removemessage",     "Remove a scheduled message"),
    BotCommand("broadcastchannels", "Broadcast to all admin channels"),
    BotCommand("confirm",           "Confirm pending broadcast"),
    BotCommand("cancel",            "Cancel pending operation"),
]


async def _post_init(app: Application) -> None:
    """
    Called once after the bot connects.
    Registers admin-scoped commands and initializes scheduled jobs.
    """
    for admin_id in settings.admin_ids:
        try:
            await app.bot.set_my_commands(
                commands=_ADMIN_COMMANDS,
                scope=BotCommandScopeChat(chat_id=admin_id),
            )
            logger.info("Commands registered for admin %d.", admin_id)
        except Exception as exc:
            # Admin may not have started the bot yet – harmless
            logger.warning("Could not set commands for admin %d: %s", admin_id, exc)

    # Restore scheduled daily messages from config
    initialize_schedules(app)


def build_app() -> Application:
    app = (
        Application.builder()
        .token(settings.bot_token)
        .post_init(_post_init)          # registers "/" suggestions on startup
        .build()
    )

    # Join requests (public)
    app.add_handler(ChatJoinRequestHandler(handle_join_request))

    # Admin commands
    app.add_handler(CommandHandler("start",      handle_start))
    app.add_handler(CommandHandler("stats",      handle_stats))
    app.add_handler(CommandHandler("users",      handle_users))
    app.add_handler(CommandHandler("broadcast",  handle_broadcast))
    app.add_handler(CommandHandler("addchannel", handle_add_channel))
    app.add_handler(CommandHandler("setwelcome", handle_setwelcome))

    # Schedule commands
    app.add_handler(CommandHandler("setmessage",        handle_setmessage))
    app.add_handler(CommandHandler("settime",           handle_settime))
    app.add_handler(CommandHandler("listmessages",      handle_listmessages))
    app.add_handler(CommandHandler("removemessage",     handle_removemessage))

    # Channel broadcast commands
    app.add_handler(CommandHandler("broadcastchannels", handle_broadcast_channels))
    app.add_handler(CommandHandler("confirm",           handle_confirm))
    app.add_handler(CommandHandler("cancel",            handle_cancel))
    app.add_handler(CommandHandler("stats",             handle_stats))

    # Catch-all for admin messages (used for /addchannel input)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_admin_message))

    return app


async def _run() -> None:
    app = build_app()
    async with app:
        await app.updater.start_polling(drop_pending_updates=True)
        await app.start()
        logger.info("Bot is running. Press Ctrl+C to stop.")
        await asyncio.Event().wait()    # block until KeyboardInterrupt / SIGTERM


if __name__ == "__main__":
    logger.info("Bot starting… admins=%s", settings.admin_ids)
    try:
        # asyncio.run() creates a fresh event loop – required on Python 3.12+
        asyncio.run(_run())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
