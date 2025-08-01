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
from handlers.cancel import handle_cancel_selection
from handlers.cancel_all import (
    start_cancel_menu,
    handle_cancel_all,
)
from handlers.admin import (
    all_bookings_admin,
    user_bookings_list,
    show_all_user_bookings,
)
from handlers.menu_router import handle_main_menu


def main() -> None:
    app = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .post_init(set_bot_commands)
        .build()
    )

    # ──────────── Команди ────────────
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("book", start_booking))
    app.add_handler(CommandHandler("cancel", start_cancel_menu))
    app.add_handler(CommandHandler("mybookings", show_user_bookings))
    app.add_handler(CommandHandler("adminbookings", all_bookings_admin))
    app.add_handler(CommandHandler("user_bookings", user_bookings_list))

    # ──────────── Callback-кнопки ────────────
    # Головне меню
    app.add_handler(CallbackQueryHandler(handle_main_menu, pattern=r"^menu_"))

    # Бронювання (дата / час / підтвердження / відміна)
    app.add_handler(
        CallbackQueryHandler(
            handle_slot_selection,
            pattern=r"^(date_|slot_|confirm_booking|confirm_month|cancel_book)",
        )
    )

    # Покрокове скасування конкретних слотів
    app.add_handler(
        CallbackQueryHandler(
            handle_cancel_selection,
            pattern=r"^(cdate_|cslot_|confirm_cancel|cancel_cancel)",
        )
    )

    # Меню масових скасувань
    app.add_handler(
        CallbackQueryHandler(
            handle_cancel_all,
            #  🔥 виправлений патерн: дозволяє ID після cau_,
            #  та прибрано $, щоб ловити можливі суфікси-підтвердження
            pattern=(
                r"^(cancel_pick_dates"
                r"|confirm_cancel_all_self"
                r"|pick_cancel_user"
                r"|cau_\d+"
                r"|confirm_cancel_all_all"
                r"|back_cancel_all"
                r"|cancel_cancel_all)"
            ),
        )
    )

    # Перегляд бронювань конкретного користувача (адмін)
    app.add_handler(CallbackQueryHandler(show_all_user_bookings, pattern=r"^ub_\d+$"))

    print("✅ Бот запущено. Чекаю команди…")
    app.run_polling()


if __name__ == "__main__":
    main()
