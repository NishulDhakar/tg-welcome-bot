import logging
from telegram.ext import Application, CommandHandler, ChatJoinRequestHandler
from config import config
from handlers import handle_join_request, handle_stats, handle_broadcast, handle_list_users

# We use the logger configured in config.py or the root one
logger = logging.getLogger(__name__)

async def main():
    """Start the Telegram bot and register all event handlers."""
    
    logger.info("Initializing bot setup...")

    # Build the application using the token from config
    application = Application.builder().token(config["BOT_TOKEN"]).build()

    # Register handlers
    # Handle incoming join requests to approval-needed communities
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    
    # Administrative commands
    application.add_handler(CommandHandler("stats", handle_stats))
    application.add_handler(CommandHandler("broadcast", handle_broadcast))
    application.add_handler(CommandHandler("users", handle_list_users))


    # Log startup success
    logger.info("Bot started successfully. Waiting for events...")

    # In modern versions of PTB, run_polling can sometimes conflict with how
    # asyncio handles the loop in certain environments. Using an explicit context manager
    # or the built-in run_polling works if started correctly.
    async with application:
        await application.start()
        await application.updater.start_polling()
        # Keep it running until a stop signal
        await asyncio.Event().wait()

if __name__ == "__main__":
    try:
        import asyncio
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped by user.")

