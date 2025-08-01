from datetime import datetime
from collections import defaultdict
from typing import List, Tuple, Dict, Set

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from booking import load_data, save_data
from config import ADMIN_CHAT_ID
from utils import format_date_label

from .users import get_user_display

# ─── callback-константи ──────────────────────────────────────
PICK_DATES         = "cancel_pick_dates"
CONFIRM_SELF       = "confirm_cancel_all_self"
PICK_USER          = "pick_cancel_user"
CONFIRM_ALL_SYSTEM = "confirm_cancel_all_all"
BACK_MAIN          = "back_cancel_all"
CANCEL_ACTION      = "cancel_cancel_all"
SEL_USER_PREFIX    = "cau_"          # cau_<uid>


# ───────────────────── меню /cancel ─────────────────────────
async def start_cancel_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Відкриває головне меню скасування (підтримує команду та callback)."""
    uid = update.effective_user.id
    is_admin = uid == ADMIN_CHAT_ID

    kb = [
        [InlineKeyboardButton("📅 Скасувати обрані дати/час", callback_data=PICK_DATES)],
        [InlineKeyboardButton("❌ Скасувати всі мої бронювання", callback_data=CONFIRM_SELF)],
    ]
    if is_admin:
        kb.insert(
            1,
            [InlineKeyboardButton("🗑️ Скасувати всі бронювання користувача", callback_data=PICK_USER)],
        )
        kb.insert(
            1,
            [InlineKeyboardButton("🔥 Скасувати ВСІ бронювання", callback_data=CONFIRM_ALL_SYSTEM)],
        )
    kb.append([InlineKeyboardButton("↩️ Відміна", callback_data=CANCEL_ACTION)])

    text = "Оберіть дію:"
    if update.callback_query:                  # натиснута кнопка
        await update.callback_query.edit_message_text(
            text=text, reply_markup=InlineKeyboardMarkup(kb)
        )
    else:                                      # команда /cancel
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(kb))


# ───────────── callback-обробник меню ───────────────────────
async def handle_cancel_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cb = query.data
    uid = query.from_user.id
    is_admin = uid == ADMIN_CHAT_ID

    # ---------- перейти до вибору дат/часу -------------------
    if cb == PICK_DATES:
        kb = _build_date_buttons(uid, is_admin)
        if not kb:
            await query.edit_message_text("Немає бронювань, які можна скасувати.")
            return
        kb.append([InlineKeyboardButton("↩️ Назад", callback_data=BACK_MAIN)])
        await query.edit_message_text(
            "Оберіть дату для скасування:",
            reply_markup=InlineKeyboardMarkup(kb),
        )
        return

    # ---------- вибір користувача (адмін) --------------------
    if cb == PICK_USER and is_admin:
        user_btns = _users_with_bookings_buttons()
        if not user_btns:
            await query.edit_message_text("Немає користувачів із активними бронюваннями.")
            return
        user_btns.append([InlineKeyboardButton("↩️ Назад", callback_data=BACK_MAIN)])
        await query.edit_message_text(
            "Оберіть користувача:",
            reply_markup=InlineKeyboardMarkup(user_btns),
        )
        return

    # ---------- адмін → скасувати всі броні конкретного юзера
    if cb.startswith(SEL_USER_PREFIX) and is_admin:
        target_uid = int(cb.split("_")[1])
        cancelled = _cancel_for_user(target_uid)
        text = (
            f"❌ Скасовано всі бронювання користувача {get_user_display(target_uid)}:\n"
            + _fmt_cancelled(cancelled)
            if cancelled
            else f"У користувача {get_user_display(target_uid)} немає активних бронювань."
        )
        await query.edit_message_text(text)
        if cancelled:  # сповіщення користувачу
            try:
                await context.bot.send_message(
                    chat_id=target_uid,
                    text=("⚠️ Ваші бронювання були скасовані адміністратором:\n"
                          + _fmt_cancelled(cancelled)),
                )
            except Exception:
                pass
        return

    # ---------- повернення до меню ---------------------------
    if cb == BACK_MAIN:
        await start_cancel_menu(update, context)
        return

    # ---------- звичайний користувач → скасувати ВСЕ ---------
    if cb == CONFIRM_SELF:
        cancelled = _cancel_for_user(uid)
        msg = (
            "❌ Скасовано:\n" + _fmt_cancelled(cancelled)
            if cancelled
            else "У вас не було активних бронювань."
        )
        await query.edit_message_text(msg)
        if not is_admin and cancelled:  # повідомити адміна
            try:
                await context.bot.send_message(
                    chat_id=ADMIN_CHAT_ID,
                    text=("❌ Користувач скасував всі свої бронювання\n"
                          f"👤 {get_user_display(uid)}\n"
                          + _fmt_cancelled(cancelled)),
                )
            except Exception:
                pass
        return

    # ---------- адмін → скасувати ВСЕ в системі --------------
    if cb == CONFIRM_ALL_SYSTEM and is_admin:
        cancelled_map = _cancel_all_system()
        total = sum(len(v) for v in cancelled_map.values())
        await query.edit_message_text(
            f"🔥 Всі бронювання ({total}) успішно скасовано."
            if total
            else "Не було активних бронювань."
        )
        for tgt_uid, pairs in cancelled_map.items():  # сповіщення кожному
            try:
                await context.bot.send_message(
                    chat_id=tgt_uid,
                    text=("⚠️ Усі ваші бронювання були скасовані адміністратором:\n"
                          + _fmt_cancelled(pairs)),
                )
            except Exception:
                pass
        return

    # ---------- відміна дії ----------------------------------
    if cb == CANCEL_ACTION:
        await query.edit_message_text("Дію скасовано.")
        return


# ───────────────────── helpers ─────────────────────
def _build_date_buttons(uid: int, is_admin: bool) -> List[List[InlineKeyboardButton]]:
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
            [InlineKeyboardButton(format_date_label(date_obj), callback_data=f"cdate_{date_str}")]
        )
    return keyboard


def _cancel_for_user(uid: int) -> List[Tuple[str, str]]:
    data = load_data()
    cancelled = []
    for date, slots in list(data.items()):
        for time, val in list(slots.items()):
            booked_uid = val["id"] if isinstance(val, dict) else int(val)
            if booked_uid == uid:
                del data[date][time]
                cancelled.append((date, time))
        if not data.get(date):
            data.pop(date, None)
    if cancelled:
        save_data(data)
    return cancelled


def _cancel_all_system() -> Dict[int, List[Tuple[str, str]]]:
    data = load_data()
    cancelled_map: Dict[int, List[Tuple[str, str]]] = defaultdict(list)
    for date, slots in data.items():
        for time, val in slots.items():
            uid = val["id"] if isinstance(val, dict) else int(val)
            cancelled_map[uid].append((date, time))
    if cancelled_map:
        save_data({})
    return cancelled_map


def _fmt_cancelled(pairs: List[Tuple[str, str]]) -> str:
    if not pairs:
        return ""
    grouped: Dict[str, List[str]] = defaultdict(list)
    for d, t in pairs:
        grouped[d].append(t)
    return "\n".join(
        f"📅 {format_date_label(datetime.strptime(d, '%Y-%m-%d'))}: {', '.join(sorted(ts))}"
        for d, ts in sorted(grouped.items())
    )


def _users_with_bookings_buttons() -> List[List[InlineKeyboardButton]]:
    data = load_data()
    uids: Set[int] = {
        int(v["id"] if isinstance(v, dict) else v)
        for slots in data.values()
        for v in slots.values()
    }
    return [
        [InlineKeyboardButton(get_user_display(uid), callback_data=f"{SEL_USER_PREFIX}{uid}")]
        for uid in sorted(uids)
    ]
