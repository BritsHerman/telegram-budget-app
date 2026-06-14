from telebot import types

from src.bot_instance import bot
from src.db.categories import get_categories
from src.db.users import resolve_user
from src.handlers.menus import send_main_menu, track_menu_message


@bot.message_handler(commands=["start"])
def handle_start(message):
    user = resolve_user(message.from_user)
    chat_id = message.chat.id

    has_categories = (
        get_categories(user["id"], "expense") or
        get_categories(user["id"], "income")
    )

    if not has_categories:
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("🚀 Set up my categories", callback_data="main_menu_setup"))
        markup.add(types.InlineKeyboardButton("Skip for now", callback_data="back_to_main"))
        msg = bot.send_message(
            chat_id,
            "👋 *Welcome to your Finance Superhero bot!*\n\n"
            "It looks like this is your first time here. Here's how to get started:\n\n"
            "1. Go to *Setup → Add Category* and create your expense categories (e.g. Groceries, Petrol)\n"
            "2. Add your income categories (e.g. Salary)\n"
            "3. Set monthly *budget amounts* for your expense categories\n"
            "4. Start recording transactions!\n\n"
            "Tap below to jump straight to Setup:",
            parse_mode="Markdown",
            reply_markup=markup,
        )
        track_menu_message(chat_id, msg.message_id)
    else:
        send_main_menu(chat_id)
