from datetime import datetime
from typing import Set

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from booking import cancel_slot, load_data
from config import ADMIN_CHAT_ID
from utils import format_date_label

from .users import get_user_display

DATE_KEY = "cancel_date"
SEL_KEY = "cancel_selected"


# ────────────────────────── helpers ──────────────────────────
def _build_cancel_keyboard(
    date_str: str,
    uid: int,
    is_admin: bool,
    selected: Set[str],
) -> InlineKeyboardMarkup:
    data = load_data()
    buttons = []

    for t, val in data.get(date_str, {}).items():
        booked_uid = val["id"] if isinstance(val, dict) else int(val)
        if not is_admin and booked_uid != uid:
            continue

        label = f"✅ {t}" if t in selected else t
        buttons.append(
            InlineKeyboardButton(label, callback_data=f"cslot_{date_str}_{t}")
        )

    keyboard = [buttons[i : i + 4] for i in range(0, len(buttons), 4)]
    if selected:
        keyboard.append(
            [InlineKeyboardButton("❌ Підтвердити", callback_data="confirm_cancel")]
        )
    keyboard.append([InlineKeyboardButton("↩️ Вийти", callback_data="cancel_cancel")])

    return InlineKeyboardMarkup(keyboard)


# ─────────────────────── /cancel старт ───────────────────────
async def start_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    is_admin = uid == ADMIN_CHAT_ID
    data = load_data()
    keyboard = []

    for date_str, slots in data.items():
        if not is_admin and all(
            (int(v.get("id", v)) if isinstance(v, dict) else int(v)) != uid
            for v in slots.values()
        ):
            continue

        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        except ValueError:
            continue

        keyboard.append(
            [
                InlineKeyboardButton(
                    format_date_label(date_obj), callback_data=f"cdate_{date_str}"
                )
            ]
        )

    if not keyboard:
        await update.message.reply_text("Немає бронювань, які можна скасувати.")
        return

    await update.message.reply_text(
        "Оберіть дату:", reply_markup=InlineKeyboardMarkup(keyboard)
    )


# ───────────── обробка callback'ів скасування ────────────────
async def handle_cancel_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cb = query.data
    uid = query.from_user.id
    is_admin = uid == ADMIN_CHAT_ID

    # ── крок 1: обрано дату ───────────────────────────────────
    if cb.startswith("cdate_"):
        date_str = cb.split("_")[1]
        context.user_data[DATE_KEY] = date_str
        context.user_data[SEL_KEY] = set()

        await query.edit_message_text(
            "Оберіть час (можна декілька):",
            reply_markup=_build_cancel_keyboard(date_str, uid, is_admin, set()),
        )
        return

    # ── крок 2: перемикаємо час ───────────────────────────────
    if cb.startswith("cslot_"):
        _, date_str, t = cb.split("_")
        selected: Set[str] = context.user_data.get(SEL_KEY, set())

        if t in selected:
            selected.remove(t)
        else:
            selected.add(t)
        context.user_data[SEL_KEY] = selected

        await query.edit_message_reply_markup(
            reply_markup=_build_cancel_keyboard(date_str, uid, is_admin, selected)
        )
        return

    # ── крок 3: підтвердження ─────────────────────────────────
    if cb == "confirm_cancel":
        date_str = context.user_data.get(DATE_KEY)
        selected: Set[str] = context.user_data.get(SEL_KEY, set())

        if not date_str or not selected:
            await query.edit_message_text("Нічого не вибрано для скасування.")
            return

        cancelled, failed = [], []
        for t in selected:
            res = cancel_slot(date_str, t, uid, is_admin=is_admin)
            if res is not None:
                cancelled.append((t, res))
            else:
                failed.append(t)

        # повідомлення ініціатору
        msg = []
        if cancelled:
            times = ", ".join(sorted(t for t, _ in cancelled))
            msg.append(f"❌ Скасовано: {times}")
        if failed:
            msg.append(f"⚠️ Не вдалося: {', '.join(sorted(failed))}")
        await query.edit_message_text("\n".join(msg) or "Операцію скасовано.")

        # адміну деталі
        if cancelled:
            for t, cancelled_uid in cancelled:
                try:
                    await context.bot.send_message(
                        chat_id=ADMIN_CHAT_ID,
                        text=(
                            "❌ Скасовано бронювання!\n"
                            f"👤 {get_user_display(cancelled_uid)}\n"
                            f"📅 {date_str}  🕒 {t}"
                        ),
                    )
                except Exception:
                    pass

                # якщо адмін скасовує бронь не свою — сповіщаємо користувача
                if is_admin and cancelled_uid != uid:
                    try:
                        await context.bot.send_message(
                            chat_id=cancelled_uid,
                            text=(
                                f"⚠️ Ваше бронювання на {date_str} о {t} "
                                "було скасовано адміністратором."
                            ),
                        )
                    except Exception:
                        pass

        # очищаємо
        context.user_data.pop(DATE_KEY, None)
        context.user_data.pop(SEL_KEY, None)
        return

    # ── вихід без дії ─────────────────────────────────────────
    if cb == "cancel_cancel":
        await query.edit_message_text("Скасування перервано.")
        context.user_data.pop(DATE_KEY, None)
        context.user_data.pop(SEL_KEY, None)
