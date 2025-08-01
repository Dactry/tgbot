from datetime import datetime, timedelta
from typing import Set, List, Tuple

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from booking import book_slot, is_slot_available, load_data
from config import ADMIN_CHAT_ID
from constants import AVAILABLE_TIMES
from utils import format_date_label

from .users import add_user_if_not_exists, get_user_display

# ─────────── ключі в user_data ───────────
DATE_KEY = "booking_date"
SEL_KEY = "booking_selected"


# ────────────────────────── helpers ──────────────────────────
def _build_time_keyboard(date_str: str, selected: Set[str]) -> InlineKeyboardMarkup:
    """Клавіатура вибору годин + кнопки підтвердження."""
    data = load_data()
    btns = []

    for t in AVAILABLE_TIMES:
        if t in data.get(date_str, {}):
            continue
        label = f"✅ {t}" if t in selected else t
        btns.append(InlineKeyboardButton(label, callback_data=f"slot_{date_str}_{t}"))

    keyboard = [btns[i : i + 4] for i in range(0, len(btns), 4)]

    if selected:
        keyboard.append(
            [
                InlineKeyboardButton("✅ Лише цей день", callback_data="confirm_booking"),
                InlineKeyboardButton("📅 На місяць", callback_data="confirm_month"),
            ]
        )
    keyboard.append([InlineKeyboardButton("↩️ Скасувати", callback_data="cancel_book")])
    return InlineKeyboardMarkup(keyboard)


def _dates_till_month_end(start: datetime) -> List[datetime]:
    """Список дат (крок = 7 днів) до кінця місяця, не включаючи першу."""
    dates = []
    d = start + timedelta(days=7)
    while d.month == start.month:
        dates.append(d)
        d += timedelta(days=7)
    return dates


def _apply_bookings(
    date_times: List[Tuple[str, str]], user_id: int
) -> Tuple[List[Tuple[str, str]], List[Tuple[str, str]]]:
    """
    Пробує забронювати всі пари (date, time).  
    Повертає (booked, failed) списками таких же пар.
    """
    booked, failed = [], []
    for d, t in date_times:
        if is_slot_available(d, t):
            book_slot(d, t, user_id)
            booked.append((d, t))
        else:
            failed.append((d, t))
    return booked, failed


# ───────────────────────── /book ─────────────────────────
async def start_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_day = datetime.now()
    data = load_data()
    kb = []

    for i in range(7):
        d = current_day + timedelta(days=i)
        d_str = d.strftime("%Y-%m-%d")
        if any(t not in data.get(d_str, {}) for t in AVAILABLE_TIMES):
            kb.append([InlineKeyboardButton(format_date_label(d), callback_data=f"date_{d_str}")])

    if not kb:
        await update.message.reply_text("Немає доступних дат для бронювання 😔")
        return

    await update.message.reply_text("Оберіть дату:", reply_markup=InlineKeyboardMarkup(kb))


# ───────────── callback'и бронювання ─────────────
async def handle_slot_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cb = query.data
    user = update.effective_user
    uid = user.id

    # крок 1 — вибір дати
    if cb.startswith("date_"):
        date_str = cb.split("_")[1]
        context.user_data[DATE_KEY] = date_str
        context.user_data[SEL_KEY] = set()
        await query.edit_message_text(
            "Оберіть час (можна декілька):", reply_markup=_build_time_keyboard(date_str, set())
        )
        return

    # крок 2 — перемикання часу
    if cb.startswith("slot_"):
        _, date_str, t = cb.split("_")
        sel: Set[str] = context.user_data.get(SEL_KEY, set())
        sel.remove(t) if t in sel else sel.add(t)
        context.user_data[SEL_KEY] = sel
        await query.edit_message_reply_markup(reply_markup=_build_time_keyboard(date_str, sel))
        return

    # ---- підтвердження (один день) ----
    if cb == "confirm_booking":
        await _finalize_booking(query, context, monthly=False)
        return

    # ---- підтвердження (до кінця місяця) ----
    if cb == "confirm_month":
        await _finalize_booking(query, context, monthly=True)
        return

    # вихід без дії
    if cb == "cancel_book":
        await query.edit_message_text("Бронювання скасовано.")
        context.user_data.pop(DATE_KEY, None)
        context.user_data.pop(SEL_KEY, None)


# ───────────────────── finalize helper ─────────────────────
async def _finalize_booking(query, context, *, monthly: bool):
    """Реалізує бронювання (one-shot або повторне)."""
    user = query.from_user
    uid = user.id
    date_str = context.user_data.get(DATE_KEY)
    selected: Set[str] = context.user_data.get(SEL_KEY, set())

    if not date_str or not selected:
        await query.edit_message_text("Нічого не вибрано для бронювання.")
        return

    add_user_if_not_exists(uid, user.first_name, user.username)

    start_date = datetime.strptime(date_str, "%Y-%m-%d")
    target_pairs = [(date_str, t) for t in selected]

    if monthly:
        extra_dates = _dates_till_month_end(start_date)
        for ex_date in extra_dates:
            d_str = ex_date.strftime("%Y-%m-%d")
            target_pairs.extend((d_str, t) for t in selected)

    booked, failed = _apply_bookings(target_pairs, uid)

    # готуємо відповіді
    def fmt(pairs):
        grouped = {}
        for d, t in pairs:
            grouped.setdefault(d, []).append(t)
        return [
            f"📅 {format_date_label(datetime.strptime(d,'%Y-%m-%d'))}: "
            + ", ".join(sorted(ts))
            for d, ts in grouped.items()
        ]

    msg_parts = []
    if booked:
        msg_parts.append("✅ Заброньовано:\n" + "\n".join(fmt(booked)))
    if failed:
        msg_parts.append("⚠️ Вже зайняті:\n" + "\n".join(fmt(failed)))

    await query.edit_message_text("\n\n".join(msg_parts))

    # сповіщаємо адміна лише про успішні слоти
    if booked:
        lines = fmt(booked)
        try:
            await context.bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text="🆕 Нова бронь!\n"
                f"👤 {get_user_display(uid)}\n"
                + "\n".join(lines),
            )
        except Exception:
            pass

    # чистимо state
    context.user_data.pop(DATE_KEY, None)
    context.user_data.pop(SEL_KEY, None)


# ─────────────── /mybookings ────────────────
async def show_user_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    data = load_data()

    grouped = {}
    for date, slots in data.items():
        user_times = [
            t
            for t, v in slots.items()
            if (int(v.get("id", v)) if isinstance(v, dict) else int(v)) == uid
        ]
        if user_times:
            grouped[date] = user_times

    if grouped:
        lines = [
            f"📅 {format_date_label(datetime.strptime(d, '%Y-%m-%d'))}: "
            + ", ".join(sorted(ts))
            for d, ts in sorted(grouped.items())
        ]
        await update.message.reply_text("Ваші активні бронювання:\n\n" + "\n".join(lines))
    else:
        await update.message.reply_text("У вас немає активних бронювань 😌")
