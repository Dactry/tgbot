from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from datetime import datetime, timedelta
from booking import is_slot_available, book_slot, load_data, save_data
from constants import AVAILABLE_TIMES
from utils import format_date_label
from handlers.users import add_user_if_not_exists
from config import ADMIN_CHAT_ID


async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = []
    today = datetime.now()
    data = load_data()

    for i in range(7):
        day = today + timedelta(days=i)
        date_str = day.strftime('%Y-%m-%d')
        booked_slots = data.get(date_str, {})

        available = [t for t in AVAILABLE_TIMES if t not in booked_slots]
        if available:
            keyboard.append([
                InlineKeyboardButton(
                    format_date_label(day),
                    callback_data=f"date_{date_str}"
                )
            ])

    if not keyboard:
        text = "Наразі немає доступних дат для бронювання."
    else:
        text = "Оберіть дату:"

    # 👇 Виправлення: підтримка як message, так і callback_query
    target = update.message or update.callback_query.message
    await target.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def handle_slot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = load_data()
    user_id = query.from_user.id
    text = ""
    kb = []

    if query.data.startswith("date_"):
        date = query.data.split("_", 1)[1]
        context.user_data["booking_date"] = date
        context.user_data["booking_selected"] = set()

        kb = _build_time_keyboard(date, set())
        text = f"Оберіть час на {format_date_label(datetime.strptime(date, '%Y-%m-%d'))}:"

    elif query.data.startswith("slot_"):
        _, date, time = query.data.split("_")
        selected = context.user_data.get("booking_selected", set())

        if time in selected:
            selected.remove(time)
        else:
            selected.add(time)

        context.user_data["booking_selected"] = selected
        kb = _build_time_keyboard(date, selected)
        text = f"Обрано: {', '.join(sorted(selected)) or 'нічого'}"

    elif query.data == "confirm_booking":
        await _finalize_booking(query, context, monthly=False)
        return
    elif query.data == "confirm_month":
        await _finalize_booking(query, context, monthly=True)
        return
    elif query.data == "cancel_book":
        context.user_data.pop("booking_date", None)
        context.user_data.pop("booking_selected", None)
        await query.edit_message_text("Бронювання скасовано.")
        return

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(kb))


def _build_time_keyboard(date: str, selected: set) -> list:
    data = load_data()
    booked = data.get(date, {})
    buttons = []

    for time in AVAILABLE_TIMES:
        if time in booked:
            continue

        label = f"✅ {time}" if time in selected else time
        buttons.append(InlineKeyboardButton(label, callback_data=f"slot_{date}_{time}"))

    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]

    if selected:
        rows.append([
            InlineKeyboardButton("✅ Лише цей день", callback_data="confirm_booking"),
            InlineKeyboardButton("📅 На місяць", callback_data="confirm_month")
        ])

    rows.append([InlineKeyboardButton("↩️ Скасувати", callback_data="cancel_book")])
    return rows


async def _finalize_booking(query, context, monthly: bool):
    user = query.from_user
    date_str = context.user_data.get("booking_date")
    selected = context.user_data.get("booking_selected", set())

    if not date_str or not selected:
        await query.edit_message_text("Нічого не вибрано для бронювання.")
        return

    add_user_if_not_exists(user.id, user.first_name, user.username)

    date = datetime.strptime(date_str, "%Y-%m-%d")
    date_times = [(date_str, time) for time in selected]

    if monthly:
        for i in range(1, 4):
            d = date + timedelta(days=i * 7)
            ds = d.strftime('%Y-%m-%d')
            for time in selected:
                date_times.append((ds, time))

    booked, failed = _apply_bookings(date_times, user.id)

    text_lines = []
    if booked:
        text_lines.append("✅ Заброньовано:")
        for d, t in booked:
            text_lines.append(f"{d} о {t}")

    if failed:
        text_lines.append("⚠️ Не вдалося забронювати:")
        for d, t in failed:
            text_lines.append(f"{d} о {t}")

    await query.edit_message_text("\n".join(text_lines) or "Нічого не заброньовано.")
    context.user_data.pop("booking_date", None)
    context.user_data.pop("booking_selected", None)

    if booked:
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=f"🆕 Нова бронь!\n👤 {user.first_name} (@{user.username})\n" +
                     "\n".join(f"{d} о {t}" for d, t in booked)
            )
        except:
            pass


def _apply_bookings(date_times: list, user_id: int):
    data = load_data()
    booked = []
    failed = []

    for date, time in date_times:
        if is_slot_available(date, time):
            book_slot(date, time, user_id)
            booked.append((date, time))
        else:
            failed.append((date, time))

    return booked, failed


async def show_user_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = load_data()
    user_id = update.effective_user.id
    bookings = []

    for date, slots in data.items():
        times = [t for t, val in slots.items() if int(val) == user_id]
        if times:
            formatted = f"📅 {format_date_label(datetime.strptime(date, '%Y-%m-%d'))}: " + ", ".join(times)
            bookings.append(formatted)

    text = "\n".join(bookings) if bookings else "У вас немає активних бронювань."
    target = update.message or update.callback_query.message
    await target.reply_text(text)

