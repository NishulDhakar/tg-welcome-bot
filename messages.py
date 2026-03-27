import logging
from config import config

# Set up logging for this module
logger = logging.getLogger(__name__)

# String prepended to all broadcast messages for clarity
BROADCAST_PREFIX = "📢 *BROADCAST MESSAGE*\n\n"

def get_welcome_message(first_name):
    """Generate the welcome message with user's first name placeholder replaced."""
    template = config.get("WELCOME_MESSAGE", "Hey {first_name}! Welcome!")
    
    # Simple substitution to avoid errors if first_name is somehow None
    name = first_name if first_name else "there"
    message = template.replace("{first_name}", name)
    
    logger.debug(f"Generated welcome message for user: {name}")
    return message

def get_stats_message(total, today):
    """Generate a formatted statistics message for admin reporting."""
    stats_msg = (
        "📊 *Bot Statistics*\n\n"
        f"👥 Total Users: {total}\n"
        f"📅 Joined Today: {today}\n"
    )
    
    logger.debug(f"Generated stats message: Total={total}, Today={today}")
    return stats_msg

def get_user_list_message(users):
    """Generate a formatted user list for admin reporting."""
    if not users:
        return "❌ No users found in database."
    
    user_list_msg = "👤 *Recent Users in Database:*\n\n"
    
    # Limit to top 20 to avoid message size limits
    for i, user in enumerate(users[:20], 1):
        username = f"@{user.get('username')}" if user.get('username') else "No Username"
        first_name = user.get('first_name', 'Unknown')
        user_list_msg += f"{i}. {first_name} ({username}) | `{user['telegram_id']}`\n"
        
    if len(users) > 20:
        user_list_msg += f"\n...and {len(users) - 20} more users."
        
    return user_list_msg

