# Telegram Private Channel Bot

A simple, async Python Telegram bot to manage join requests, welcome new members, and provide admin statistics and broadcasting capabilities.

## Features
- ✅ **Automatic Join Request Approval**: Fast and reliable member processing.
- 💬 **Personalized Welcome Messages**: DM greetings to new members.
- 📊 **Admin Stats**: View total users and today's join count.
- 📢 **Broadcasting**: Send messages to all registered users from the admin panel.
- 🔐 **Supabase Integration**: Secure, cloud-hosted user database.

## Prerequisites
- **Python**: 3.11+
- **Database**: Supabase (Free tier works perfectly)
- **Telegram**: A bot token from @BotFather

## Setup Instructions

### 1. Database Configuration
Go to your **Supabase SQL Editor** and run the following code to create the `users` table:

```sql
create table users (
  id uuid default gen_random_uuid() primary key,
  telegram_id bigint unique not null,
  username text,
  first_name text,
  last_name text,
  status text default 'approved',
  source text default 'main_bot',
  joined_at timestamp with time zone default now(),
  metadata jsonb default '{}'::jsonb
);
```

### 2. Environment Setup
Copy the example environment file and fill in your unique credentials:
```bash
cp .env.example .env
```
Ensure you have the following from Supabase and BotFather:
- `BOT_TOKEN`: Your API token.
- `CHANNEL_ID`: The ID of your private channel.
- `SUPABASE_URL`: Your project URL.
- `SUPABASE_KEY`: Your service role key.

### 3. Installation
Install the necessary Python dependencies:
```bash
pip install -r requirements.txt
```

### 4. Running the Bot
Launch the bot with:
```bash
python bot.py
```

## Admin Commands
- `/stats` - Get a detailed report on users and growth.
- `/broadcast <message>` - Send a personalized DM to all users in the database.

## Support
Built with 💖 using `python-telegram-bot` and `supabase-py`.

```
./venv/bin/python3 bot.py
```