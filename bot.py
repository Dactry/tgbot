from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
)

from config import BOT_TOKEN
from handlers.base import start, help_command, set_bot_commands
from handlers.booking import (
    start_booking,
    handle_slot_selection,
    show_user_bookings,
)
from handlers.cancel import handle_cancel_selection          # покрокове скасування
from handlers.cancel_all import (                             # меню + масове
    start_cancel_menu,
    handle_cancel_all,
)
from handlers.admin import (
    all_bookings_admin,
    user_bookings_list,
    show_all_user_bookings,
)


# ───────────────────────── post_startup ──────────────────────
async def post_startup(app):
    await app.bot.delete_webhook(drop_pending_updates=True)
    await set_bot_commands(app)
    print("🔄 Webhook очищено, команди оновлено, бот запущений.")


app = (
    ApplicationBuilder()
    .token(BOT_TOKEN)
    .post_init(post_startup)
    .build()
)

# ────────────────────────── Команди ──────────────────────────
app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("help", help_command))
app.add_handler(CommandHandler("book", start_booking))
app.add_handler(CommandHandler("cancel", start_cancel_menu))     # ← одне меню
app.add_handler(CommandHandler("mybookings", show_user_bookings))
app.add_handler(CommandHandler("adminbookings", all_bookings_admin))
app.add_handler(CommandHandler("user_bookings", user_bookings_list))

# ───────────────────── Callback-хендлери ─────────────────────
app.add_handler(CallbackQueryHandler(show_all_user_bookings, pattern=r"^ub_\d+$"))

# 1) Меню / масове скасування
app.add_handler(
    CallbackQueryHandler(
        handle_cancel_all,
        pattern=r"^(cancel_pick_dates|confirm_cancel_all_self|pick_cancel_user|confirm_cancel_all_all|back_cancel_all|cancel_cancel_all|cau_\d+)$",
    )
)

# 2) Покрокове скасування обраних дат/часу
app.add_handler(
    CallbackQueryHandler(
        handle_cancel_selection,
        pattern=r"^(cdate_|cslot_|confirm_cancel$|cancel_cancel$)",
    )
)

# 3) Бронювання
app.add_handler(
    CallbackQueryHandler(
        handle_slot_selection,
        pattern=r"^(date_|slot_|confirm_booking|confirm_month|cancel_book)",
    )
)

# ────────────────────────── Запуск ───────────────────────────
if __name__ == "__main__":
    app.run_polling()
