"""Functions that send or edit Telegram menus. No business logic here."""
from telebot import types

from src import state
from src.bot_instance import bot
from src.db.categories import get_categories
from src.db.transactions import get_recent_transactions


def clear_last_menu(chat_id: int) -> None:
    """Remove inline buttons from the last tracked menu message for this chat."""
    mid = state.last_menu_message_id.pop(chat_id, None)
    if mid:
        try:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=mid, reply_markup=None)
        except Exception:
            pass


def track_menu_message(chat_id: int, message_id: int) -> None:
    """Mark a message as the current active keyboard so it can be cleared later."""
    state.last_menu_message_id[chat_id] = message_id


def send_main_menu(chat_id: int, text: str = "👋 Welcome! How can I help you today?") -> None:
    clear_last_menu(chat_id)
    markup = types.InlineKeyboardMarkup()
    markup.add(
        types.InlineKeyboardButton("📅 Transactions", callback_data="main_menu_daily"),
        types.InlineKeyboardButton("⚙️ Setup",        callback_data="main_menu_setup"),
        types.InlineKeyboardButton("📊 Summary",      callback_data="main_menu_summary"),
        types.InlineKeyboardButton("❓ Help",          callback_data="main_menu_help"),
    )
    msg = bot.send_message(chat_id, text, reply_markup=markup)
    track_menu_message(chat_id, msg.message_id)


def send_transactions_menu(chat_id: int, message_id: int | None = None) -> None:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("💸 Expense",     callback_data="show_expense_cats"),
        types.InlineKeyboardButton("💰 Income",      callback_data="show_income_cats"),
        types.InlineKeyboardButton("📋 History",     callback_data="view_history"),
        types.InlineKeyboardButton("🔙 Back",        callback_data="back_to_main"),
    )
    _send_or_edit("📝 What would you like to do?", chat_id, message_id, markup)


def cancel_markup() -> types.InlineKeyboardMarkup:
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ Cancel", callback_data="cancel_prompt"))
    return markup


def send_setup_menu(chat_id: int, message_id: int | None = None) -> None:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➕ Add Category",      callback_data="add_cat_menu"),
        types.InlineKeyboardButton("❌ Remove Category",   callback_data="remove_cat_menu"),
        types.InlineKeyboardButton("👀 View Categories",   callback_data="view_cats"),
        types.InlineKeyboardButton("🗑️ Delete Transaction", callback_data="delete_tx_menu"),
        types.InlineKeyboardButton("💰 Budget Amounts",    callback_data="budget_amounts_menu"),
        types.InlineKeyboardButton("📅 Set Budget Day",    callback_data="set_budget_day"),
        types.InlineKeyboardButton("🔙 Back",              callback_data="back_to_main"),
    )
    _send_or_edit("⚙️ Category and Transaction Management:", chat_id, message_id, markup)


def send_add_category_type_menu(chat_id: int, message_id: int | None = None) -> None:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➖ Expense Category", callback_data="add_cat_type_expense"),
        types.InlineKeyboardButton("➕ Income Category",  callback_data="add_cat_type_income"),
        types.InlineKeyboardButton("🔙 Back",             callback_data="back_to_setup"),
    )
    _send_or_edit("📝 What type of category would you like to add?", chat_id, message_id, markup)


def send_remove_category_type_menu(chat_id: int, message_id: int | None = None) -> None:
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("➖ Expense Category", callback_data="remove_cat_type_expense"),
        types.InlineKeyboardButton("➕ Income Category",  callback_data="remove_cat_type_income"),
        types.InlineKeyboardButton("🔙 Back",             callback_data="back_to_setup"),
    )
    _send_or_edit("📝 What type of category would you like to remove?", chat_id, message_id, markup)


def show_categories_for_transaction(
    chat_id: int, message_id: int | None, user_id: str, category_type: str
) -> None:
    categories = get_categories(user_id, category_type)
    if not categories:
        text = f"⚠️ No {category_type} categories yet. Use Setup > Add Category first!"
        _send_or_edit(text, chat_id, message_id)
        send_transactions_menu(chat_id, message_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(cat["name"], callback_data=f"add_tx_{cat['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_daily"))

    emoji = "💸" if category_type == "expense" else "💰"
    _send_or_edit(f"{emoji} Select a {category_type} category:", chat_id, message_id, markup)


def show_categories_to_remove(
    chat_id: int, message_id: int, user_id: str, category_type: str
) -> None:
    categories = get_categories(user_id, category_type)
    if not categories:
        bot.edit_message_text(
            f"⚠️ No {category_type} categories to remove.", chat_id, message_id
        )
        send_remove_category_type_menu(chat_id, message_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    for cat in categories:
        markup.add(types.InlineKeyboardButton(cat["name"], callback_data=f"remove_cat_{cat['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_remove_cat_type"))

    bot.edit_message_text(
        f"📝 Select a {category_type} category to remove:", chat_id, message_id, reply_markup=markup
    )


def show_categories_for_budget(
    chat_id: int, message_id: int | None, user_id: str
) -> None:
    expense_cats = get_categories(user_id, "expense")
    income_cats = get_categories(user_id, "income")

    if not expense_cats and not income_cats:
        _send_or_edit("⚠️ No categories yet. Add some via Setup > Add Category.", chat_id, message_id)
        send_setup_menu(chat_id, message_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    if expense_cats:
        markup.add(types.InlineKeyboardButton("── Expenses ──", callback_data="ignore_header"))
        for cat in expense_cats:
            markup.add(types.InlineKeyboardButton(cat["name"], callback_data=f"budget_cat_{cat['id']}"))
    if income_cats:
        markup.add(types.InlineKeyboardButton("── Income ──", callback_data="ignore_header"))
        for cat in income_cats:
            markup.add(types.InlineKeyboardButton(cat["name"], callback_data=f"budget_cat_{cat['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_setup"))

    _send_or_edit("💰 Select a category to set or update its budget:", chat_id, message_id, markup)


def show_delete_transaction_menu(
    chat_id: int, message_id: int | None, user_id: str
) -> None:
    recent = get_recent_transactions(user_id, limit=10)
    if not recent:
        _send_or_edit("⚠️ No transactions found to delete.", chat_id, message_id)
        send_setup_menu(chat_id, message_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=1)
    for tx in recent:
        date_str = tx["transacted_at"][:10]
        emoji = "💸" if tx["type"] == "expense" else "💰"
        label = f"{emoji} {tx['categories']['name']}  R{float(tx['amount']):.2f}  {date_str}"
        markup.add(types.InlineKeyboardButton(label, callback_data=f"confirm_delete_{tx['id']}"))
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_setup"))

    _send_or_edit("🗑️ Select a transaction to delete:", chat_id, message_id, markup)


# --- internal helper ---

def _send_or_edit(
    text: str,
    chat_id: int,
    message_id: int | None,
    markup: types.InlineKeyboardMarkup | None = None,
) -> None:
    if message_id:
        bot.edit_message_text(text, chat_id, message_id, reply_markup=markup)
    else:
        clear_last_menu(chat_id)
        msg = bot.send_message(chat_id, text, reply_markup=markup)
        if markup:
            track_menu_message(chat_id, msg.message_id)
