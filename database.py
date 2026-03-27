import logging
import datetime
from supabase import create_client, Client
from config import config

# Set up logging for this module
logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = create_client(config["SUPABASE_URL"], config["SUPABASE_KEY"])

async def save_user(telegram_id, username, first_name, last_name, source="main_bot"):
    """Upsert user information to the Supabase database."""
    try:
        data = {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "last_name": last_name,
            "source": source,
            "status": "approved"
        }
        
        # Use upsert to insert or update based on unique telegram_id constraint
        result = supabase.table("users").upsert(data, on_conflict="telegram_id").execute()
        logger.info(f"User {telegram_id} saved/updated successfully in the database.")
        return result
    except Exception as e:
        logger.error(f"Error saving user {telegram_id} to database: {e}")
        return None

async def get_all_users():
    """Retrieve all users stored in the database."""
    try:
        response = supabase.table("users").select("telegram_id, username, first_name").execute()
        logger.info(f"Retrieved {len(response.data)} users from the database.")
        return response.data
    except Exception as e:
        logger.error(f"Error fetching all users from database: {e}")
        return []

async def get_stats():
    """Return total user count and today's join count from the database."""
    try:
        # Total users count
        total_response = supabase.table("users").select("id", count="exact").execute()
        total_count = total_response.count if total_response.count is not None else 0
        
        # joined_at column defaults to now() which is UTC in Supabase
        # Today's joins filter
        today_start = datetime.datetime.now(datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        today_response = supabase.table("users") \
                        .select("id", count="exact") \
                        .gte("joined_at", today_start) \
                        .execute()
        
        today_count = today_response.count if today_response.count is not None else 0
        
        logger.info(f"Stats retrieved - Total: {total_count}, Today: {today_count}")
        return total_count, today_count
    except Exception as e:
        logger.error(f"Error getting database stats: {e}")
        return 0, 0
