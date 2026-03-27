import asyncio
import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

async def test_db():
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    
    print(f"Connecting to: {url}")
    supabase = create_client(url, key)
    
    try:
        # Check if we can select from users
        print("Fetching users...")
        response = supabase.table("users").select("*").execute()
        print(f"Success! Found {len(response.data)} users.")
        for user in response.data:
            print(user)
            
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_db())
