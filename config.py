import os
import logging
from dotenv import load_dotenv

# Configure basic logging as early as possible
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Load .env file
load_dotenv()

def load_config():
    """Load and validate all environment variables, returning a config dict."""
    
    # Required parameters
    bot_token = os.getenv("BOT_TOKEN")
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_KEY")
    channel_id = os.getenv("CHANNEL_ID")
    admin_ids_str = os.getenv("ADMIN_IDS", "")
    welcome_message = os.getenv("WELCOME_MESSAGE", "Hey {first_name}! Welcome!")

    # Check for missing crucial environment variables
    missing_vars = []
    if not bot_token:
        missing_vars.append("BOT_TOKEN")
    if not supabase_url:
        missing_vars.append("SUPABASE_URL")
    if not supabase_key:
        missing_vars.append("SUPABASE_KEY")
    if not channel_id:
        missing_vars.append("CHANNEL_ID")

    if missing_vars:
        error_msg = f"Missing environment variables: {', '.join(missing_vars)}. Please check your .env file."
        logger.error(error_msg)
        raise EnvironmentError(error_msg)

    # Parse ADMIN_IDS into a list of integers
    admin_ids = []
    if admin_ids_str:
        try:
            admin_ids = [int(id.strip()) for id in admin_ids_str.split(",") if id.strip()]
        except ValueError:
            logger.warning("Failed to parse ADMIN_IDS properly. Ensure it's a comma-separated list of integers.")

    return {
        "BOT_TOKEN": bot_token,
        "SUPABASE_URL": supabase_url,
        "SUPABASE_KEY": supabase_key,
        "CHANNEL_ID": channel_id,
        "ADMIN_IDS": admin_ids,
        "WELCOME_MESSAGE": welcome_message
    }

# Export single config object
config = load_config()
