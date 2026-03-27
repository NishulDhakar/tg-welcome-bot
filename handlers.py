import logging
from telegram import Update, constants
from telegram.ext import ContextTypes
from config import config
from database import save_user, get_all_users, get_stats
from messages import get_welcome_message, get_stats_message, BROADCAST_PREFIX, get_user_list_message

# Set up logging for this module
logger = logging.getLogger(__name__)

async def check_admin(user_id):
    """Return True if user_id is in ADMIN_IDS from config list."""
    admin_list = config.get("ADMIN_IDS", [])
    if user_id in admin_list:
        logger.info(f"User {user_id} verified as admin.")
        return True
    
    logger.warning(f"User {user_id} denied access for admin function.")
    return False

# ... keep existing handle_join_request, handle_stats, handle_broadcast ...

async def handle_list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /users command for authorized admins."""
    user_id = update.effective_user.id
    
    if not await check_admin(user_id):
        return

    try:
        users = await get_all_users()
        user_list_msg = get_user_list_message(users)
        await update.message.reply_text(user_list_msg, parse_mode=constants.ParseMode.MARKDOWN)
        logger.info(f"User list delivered to admin {user_id}.")
    except Exception as e:
        logger.error(f"Error handling /users command: {e}")
        await update.message.reply_text("❌ Error retrieving user list.")


async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ChatJoinRequest events to approve users and notify them in DMs."""
    request = update.chat_join_request
    if not request:
        return

    user = request.from_user
    chat_id = request.chat.id
    telegram_id = user.id
    
    # Always log incoming requests
    logger.info(f"Received join request for chat {chat_id} from {telegram_id} ({user.username}).")

    try:
        # 1. Approve the request - User is always approved first
        await request.approve()
        logger.info(f"Join request approved for {telegram_id} in chat {chat_id}.")

        # 2. Add to database (optional, don't block if database fails)
        try:
            await save_user(
                telegram_id=telegram_id,
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
                source=f"channel_{chat_id}"
            )
        except Exception as db_err:
            logger.error(f"Failed to record {telegram_id} in DB: {db_err}")

        # 3. Send welcome DM (optional, don't block)
        try:
            # Welcome message template
            welcome_text = get_welcome_message(user.first_name)
            await context.bot.send_message(chat_id=telegram_id, text=welcome_text)
            logger.info(f"Welcome DM sent to {telegram_id}.")
        except Exception as dm_err:
            # This often fails if the user hasn't started the bot or blocked it
            logger.warning(f"Could not send welcome DM to {telegram_id}: {dm_err}")

    except Exception as e:
        logger.error(f"System error handling join request for {telegram_id}: {e}")

async def handle_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command for authorized admins."""
    user_id = update.effective_user.id
    
    if not await check_admin(user_id):
        return

    try:
        total, today = await get_stats()
        stats_msg = get_stats_message(total, today)
        await update.message.reply_text(stats_msg, parse_mode=constants.ParseMode.MARKDOWN)
        logger.info(f"Stats report delivered to admin {user_id}.")
    except Exception as e:
        logger.error(f"Error handling /stats command: {e}")
        await update.message.reply_text("❌ Error retrieving statistics.")

async def handle_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /broadcast <message> to send DM to all registered users."""
    user_id = update.effective_user.id
    
    if not await check_admin(user_id):
        return

    # Extract original message (command is length of first word + 1)
    message_to_send = update.message.text.split(maxsplit=1)
    if len(message_to_send) < 2:
        await update.message.reply_text("❌ Please include a message: /broadcast Hello everyone!")
        return

    broadcast_content = f"{BROADCAST_PREFIX}{message_to_send[1]}"
    
    try:
        users = await get_all_users()
        if not users:
            await update.message.reply_text("❌ No users found in database.")
            return

        status_msg = await update.message.reply_text(f"🚀 Starting broadcast to {len(users)} users...")
        
        delivered_count = 0
        failed_count = 0
        
        for user_data in users:
            try:
                target_id = user_data["telegram_id"]
                await context.bot.send_message(
                    chat_id=target_id, 
                    text=broadcast_content, 
                    parse_mode=constants.ParseMode.MARKDOWN
                )
                delivered_count += 1
            except Exception as e:
                logger.warning(f"Failed delivery to {user_data.get('telegram_id')}: {e}")
                failed_count += 1
        
        await status_msg.edit_text(f"✅ Broadcast finished!\n\nDelivered: {delivered_count}\nFailed: {failed_count}")
        logger.info(f"Broadcast completed for admin {user_id}: {delivered_count} delivered, {failed_count} failed.")

    except Exception as e:
        logger.error(f"Fatal error during broadcast processing: {e}")
        await update.message.reply_text("❌ Broadcast failed unexpectedly.")
