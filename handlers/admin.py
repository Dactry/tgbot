from datetime import datetime
from collections import defaultdict

from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram.ext import ContextTypes

from booking import load_data
from config import ADMIN_CHAT_ID
from utils import format_date_label

from .users import load_users, get_user_display


# ───────────────────────── /adminbookings ─────────────────────────
async def all_bookings_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Виводить усі активні бронювання у зручному, згрупованому вигляді:

    📅 1 серпня 2025
      09:00 — John (@john)
      11:00 — Kate

    📅 2 серпня 2025
      10:00 — Alex
    """
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔️ У вас немає прав для цієї команди.")
        return

    data = load_data()
    if not data:
        await update.message.reply_text("Немає активних бронювань.")
        return

    # групуємо слоти за датою
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for date_str, slots in data.items():
        for time, val in slots.items():
            uid = val["id"] if isinstance(val, dict) else int(val)
            grouped[date_str].append((time, get_user_display(uid)))

    # формуємо текст
    parts: list[str] = []
    for date_str in sorted(grouped.keys()):
        date_label = format_date_label(datetime.strptime(date_str, "%Y-%m-%d"))
        parts.append(f"📅 {date_label}")
        for time, user_disp in sorted(
            grouped[date_str], key=lambda x: datetime.strptime(x[0], "%H:%M")
        ):
            parts.append(f"  {time} — {user_disp}")
        parts.append("")  # порожній рядок між датами

    target = update.message or update.callback_query.message
    await target.reply_text("\n".join(parts).rstrip())



# ───────────── /user_bookings  (quick picker) ────────────────
async def user_bookings_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показує список користувачів, у яких є бронювання."""
    if update.effective_user.id != ADMIN_CHAT_ID:
        return

    users = load_users()
    keyboard = [
        [
            InlineKeyboardButton(
                get_user_display(int(uid)),
                callback_data=f"ub_{uid}",
            )
        ]
        for uid in sorted(users.keys(), key=int)
    ]

    await update.message.reply_text(
        "Оберіть користувача:",
        reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None,
    )


# ────── показ броней вибраного користувача (для адміна) ──────
async def show_all_user_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відображає бронювання конкретного користувача у стилі /mybookings."""
    query = update.callback_query
    if not query or update.effective_user.id != ADMIN_CHAT_ID:
        return

    await query.answer()
    uid = int(query.data.split("_")[1])
    data = load_data()

    grouped: dict[str, list[str]] = defaultdict(list)
    for date, slots in data.items():
        for time, val in slots.items():
            booked_uid = val["id"] if isinstance(val, dict) else int(val)
            if booked_uid == uid:
                grouped[date].append(time)

    if grouped:
        lines = [
            f"📅 {format_date_label(datetime.strptime(date, '%Y-%m-%d'))}: "
            + ", ".join(sorted(times))
            for date, times in sorted(grouped.items())
        ]
        text = "\n".join(lines)
    else:
        text = "Немає активних бронювань."

    await query.edit_message_text(
        f"Бронювання {get_user_display(uid)}:\n{text}"
    )
