from src.bot_instance import bot
from src.db.users import resolve_user
from src.handlers.menus import send_main_menu


@bot.message_handler(commands=["start"])
def handle_start(message):
    resolve_user(message.from_user)  # ensure user row exists
    send_main_menu(message.chat.id)
