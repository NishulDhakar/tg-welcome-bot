"""
bot/messages.py
───────────────
All user-facing message templates in one place.
Edit text here without touching handler logic.
"""

from bot.config import settings

# ── Broadcast prefix ──────────────────────────────────────────────────────────
BROADCAST_PREFIX = "📢 *Broadcast*\n\n"


# ── Welcome ───────────────────────────────────────────────────────────────────
def welcome(first_name: str) -> str:
    name = first_name.strip() if first_name else "there"
    return settings.welcome_message.replace("{first_name}", name)


# ── Admin: /stats ─────────────────────────────────────────────────────────────
def stats(total: int, today: int) -> str:
    return (
        "📊 *Bot Statistics*\n\n"
        f"👥 Total users: *{total}*\n"
        f"📅 Joined today: *{today}*"
    )


# ── Admin: /users ─────────────────────────────────────────────────────────────
def user_list(users: list) -> str:
    if not users:
        return "ℹ️ No users in the database yet."

    lines = ["👤 *Registered Users*\n"]
    for i, u in enumerate(users[:50], 1):
        name = u.get("first_name") or "—"
        uname = f"@{u['username']}" if u.get("username") else "no username"
        tid = u["telegram_id"]
        lines.append(f"{i}\\. {name} ({uname}) `{tid}`")

    if len(users) > 50:
        lines.append(f"\n_…and {len(users) - 50} more_")

    return "\n".join(lines)


# ── Broadcast body ────────────────────────────────────────────────────────────
def broadcast_body(text: str) -> str:
    return f"{BROADCAST_PREFIX}{text}"
