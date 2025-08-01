from telegram import (
    Update,
    BotCommand,
    BotCommandScopeDefault,
    BotCommandScopeChat,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import ContextTypes

from config import ADMIN_CHAT_ID


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    name = user.first_name or "👋"

    buttons = [
        [
            InlineKeyboardButton("➕ Забронювати", callback_data="menu_book"),
            InlineKeyboardButton("📋 Мої броні", callback_data="menu_my"),
        ],
        [InlineKeyboardButton("❌ Скасувати", callback_data="menu_cancel")],
    ]

    if user.id == ADMIN_CHAT_ID:
        buttons.append([InlineKeyboardButton("🗂️ Усі броні", callback_data="menu_admin")])

    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"Привіт, {name}! 👋\nОберіть дію нижче:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )
    else:
        await update.message.reply_text(
            f"Привіт, {name}! 👋\nЯ допоможу забронювати або скасувати заняття.\n"
            "Оберіть дію нижче:",
            reply_markup=InlineKeyboardMarkup(buttons),
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Основні дії доступні кнопками у /start.\n"
        "Команди на випадок, якщо кнопки не видно:\n"
        " /book – забронювати\n"
        " /mybookings – список моїх бронювань\n"
        " /cancel – меню скасування\n"
        "\nАдміну додаткові:\n"
        " /adminbookings – усі броні\n"
        " /user_bookings – броні користувача"
    )


async def set_bot_commands(app):
    cmds = [
        BotCommand("start", "Головне меню"),
        BotCommand("book", "Забронювати"),
        BotCommand("mybookings", "Мої броні"),
        BotCommand("cancel", "Меню скасування"),
    ]
    await app.bot.set_my_commands(cmds, scope=BotCommandScopeDefault())
    await app.bot.set_my_commands(
        cmds
        + [
            BotCommand("adminbookings", "Усі броні"),
            BotCommand("user_bookings", "Броні користувача"),
        ],
        scope=BotCommandScopeChat(chat_id=ADMIN_CHAT_ID),
    )
