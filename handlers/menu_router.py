from telegram import Update
from telegram.ext import ContextTypes

from config import ADMIN_CHAT_ID
from handlers.booking import start_booking, show_user_bookings
from handlers.cancel_all import start_cancel_menu
from handlers.admin import all_bookings_admin
from handlers.base import start  # для menu_home


async def handle_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Роутер для callback-кнопок головного меню:
    - menu_book   → вибір дати/часу для бронювання
    - menu_my     → список особистих бронювань
    - menu_cancel → меню скасування
    - menu_admin  → усі броні (адмін)
    - menu_home   → повернення до головного меню
    """
    query = update.callback_query
    await query.answer()
    action = query.data
    uid = update.effective_user.id

    if action == "menu_book":
        await start_booking(update, context)
    elif action == "menu_my":
        await show_user_bookings(update, context)
    elif action == "menu_cancel":
        await start_cancel_menu(update, context)
    elif action == "menu_admin" and uid == ADMIN_CHAT_ID:
        await all_bookings_admin(update, context)
    elif action == "menu_home":
        await start(update, context)  # повернутися в головне меню
