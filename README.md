# Telegram Welcome Bot

Auto-accepts join requests for a private channel and sends a welcome DM.  
Admins can broadcast a message to all registered users.

---

## Features

| Feature | Description |
|---|---|
| **Auto-approve** | Instantly approves every join request to your channel |
| **Welcome DM** | Sends a personalized DM to each new member |
| **User DB** | Saves every member to Supabase |
| `/stats` | Total users + joined today |
| `/users` | List of registered users (admin only) |
| `/broadcast` | Send a DM to all users (admin only) |

---

## Setup

### 1. Clone & install

```bash
git clone <repo>
cd tg-welcome-bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env`

```env
BOT_TOKEN=<from @BotFather>
CHANNEL_ID=-100xxxxxxxxxx
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_KEY=<service role key>
ADMIN_IDS=123456789,987654321
WELCOME_MESSAGE=Hey {first_name}! Welcome 🎉
```

### 3. Supabase table

Run in the Supabase SQL editor:

```sql
create table users (
  id          bigserial primary key,
  telegram_id bigint unique not null,
  username    text,
  first_name  text,
  last_name   text,
  source      text,
  status      text default 'approved',
  joined_at   timestamptz default now()
);
```

### 4. Enable join requests

In Telegram: Channel Settings → Subscribers → enable **Join Requests**.  
Add the bot as **Administrator** with permission to **Add Members**.

### 5. Run

```bash
python bot.py
```

---

## Project structure

```
tg-welcome-bot/
├── bot/
│   ├── __init__.py
│   ├── config.py          # Settings & validation (singleton)
│   ├── database.py        # Supabase operations
│   ├── messages.py        # All user-facing message templates
│   └── handlers/
│       ├── __init__.py
│       ├── join.py        # ChatJoinRequest handler
│       └── admin.py       # /stats /users /broadcast
├── bot.py                 # Entry point
├── .env                   # Secrets (never commit)
├── .env.example
├── requirements.txt
└── README.md
```

---

## Admin commands

| Command | Description |
|---|---|
| `/stats` | Show total & today's member count |
| `/users` | List up to 50 registered users |
| `/broadcast Hello!` | Send "Hello!" to everyone in DB |