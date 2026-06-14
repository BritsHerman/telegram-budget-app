"""Handles user text replies to bot prompts (the awaiting_reply state machine)."""
from src.bot_instance import bot
from src.db.budgets import get_budget, set_budget
from src.db.categories import add_category, get_category_by_id
from src.db.transactions import add_transaction, get_spent_amount
from src.db.users import resolve_user, set_budget_day
from src.handlers.menus import send_main_menu
from src.helpers import escape_v1, get_budget_period
from src.state import awaiting_reply


def _is_awaited_reply(message) -> bool:
    chat_id = message.chat.id
    if chat_id not in awaiting_reply:
        return False
    if message.content_type != "text":
        return False
    if not message.reply_to_message:
        return False
    if message.reply_to_message.from_user.id != bot.get_me().id:
        return False
    if message.reply_to_message.message_id != awaiting_reply[chat_id]["bot_prompt_message_id"]:
        return False
    return True


def _clear_prompt(chat_id: int, state: dict) -> None:
    """Remove the cancel button from the prompt message after the user has replied."""
    mid = state.get("bot_prompt_message_id")
    if mid:
        try:
            bot.edit_message_reply_markup(chat_id=chat_id, message_id=mid, reply_markup=None)
        except Exception:
            pass


@bot.message_handler(func=_is_awaited_reply, content_types=["text"])
def process_reply(message):
    chat_id = message.chat.id
    user = resolve_user(message.from_user)
    state = awaiting_reply.get(chat_id)
    if not state:
        return

    action = state["action"]
    text = message.text.strip()

    if action == "add_transaction":
        _handle_add_transaction(chat_id, user, state, text)

    elif action == "add_category":
        _handle_add_category(chat_id, user, state, text)

    elif action == "set_budget":
        _handle_set_budget(chat_id, user, state, text)

    elif action == "set_budget_day":
        _handle_set_budget_day(chat_id, user, state, text)


# ── Action handlers ──────────────────────────────────────────────────────────

def _handle_add_transaction(chat_id: int, user: dict, state: dict, text: str) -> None:
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        bot.send_message(
            chat_id,
            "⚠️ Invalid amount. Enter a positive number (e.g. 50 or 149.99). "
            "**Reply to the original prompt again.**",
            parse_mode="Markdown",
        )
        return

    category_id = state["category_id"]
    cat = get_category_by_id(user["id"], category_id)
    if not cat:
        bot.send_message(chat_id, "⚠️ Category no longer exists. Starting over.")
        _clear_prompt(chat_id, state)
        del awaiting_reply[chat_id]
        send_main_menu(chat_id)
        return

    tx = add_transaction(user["id"], category_id, amount, cat["type"])

    budget = get_budget(user["id"], category_id)
    start, end = get_budget_period(user["budget_day"])
    spent = get_spent_amount(user["id"], category_id, start, end)

    budget_str = f"R{budget:.2f}" if budget is not None else "not set"
    word = "expense" if cat["type"] == "expense" else "income"

    lines = [
        f"✅ Recorded R{amount:.2f} as *{word}* for *{escape_v1(cat['name'])}*.",
        f"💰 Budget: {budget_str}",
        f"📈 {'Spent' if cat['type'] == 'expense' else 'Received'} this period: R{spent:.2f}",
    ]

    if cat["type"] == "expense" and budget is not None and spent > budget:
        over = spent - budget
        lines.append(f"\n⚠️ *You're R{over:.2f} over budget for {escape_v1(cat['name'])}!*")

    _clear_prompt(chat_id, state)
    del awaiting_reply[chat_id]
    bot.send_message(chat_id, "\n".join(lines), parse_mode="Markdown")
    send_main_menu(chat_id)


def _handle_add_category(chat_id: int, user: dict, state: dict, text: str) -> None:
    name = text
    category_type = state["category_type"]

    if not name:
        bot.send_message(
            chat_id,
            "⚠️ Name cannot be empty. **Reply to the original prompt again.**",
            parse_mode="Markdown",
        )
        return

    cat = add_category(user["id"], name, category_type)
    if cat is None:
        bot.send_message(
            chat_id,
            f"⚠️ *{escape_v1(name)}* already exists in {category_type} categories. "
            "Choose a different name or **reply again**.",
            parse_mode="Markdown",
        )
        return

    _clear_prompt(chat_id, state)
    del awaiting_reply[chat_id]
    bot.send_message(
        chat_id,
        f"✅ Added *{escape_v1(name)}* to {category_type} categories.",
        parse_mode="Markdown",
    )
    send_main_menu(chat_id)


def _handle_set_budget(chat_id: int, user: dict, state: dict, text: str) -> None:
    try:
        amount = float(text)
        if amount < 0:
            raise ValueError
    except ValueError:
        bot.send_message(
            chat_id,
            "⚠️ Invalid amount. Enter a non-negative number or 0 to remove the budget. "
            "**Reply to the original prompt again.**",
            parse_mode="Markdown",
        )
        return

    category_id = state["category_id"]
    cat = get_category_by_id(user["id"], category_id)
    name = cat["name"] if cat else category_id

    set_budget(user["id"], category_id, amount)

    _clear_prompt(chat_id, state)
    del awaiting_reply[chat_id]
    if amount == 0:
        bot.send_message(chat_id, f"✅ Budget for *{escape_v1(name)}* removed.", parse_mode="Markdown")
    else:
        bot.send_message(
            chat_id,
            f"✅ Budget for *{escape_v1(name)}* set to R{amount:.2f}.",
            parse_mode="Markdown",
        )
    send_main_menu(chat_id)


def _handle_set_budget_day(chat_id: int, user: dict, state: dict, text: str) -> None:
    try:
        day = int(text)
        if not 1 <= day <= 31:
            raise ValueError
    except ValueError:
        bot.send_message(
            chat_id,
            "⚠️ Please enter a whole number between 1 and 31. "
            "**Reply to the original prompt again.**",
            parse_mode="Markdown",
        )
        return

    set_budget_day(user["id"], day)
    _clear_prompt(chat_id, state)
    del awaiting_reply[chat_id]
    bot.send_message(chat_id, f"✅ Budget period start day set to *{day}*.", parse_mode="Markdown")
    send_main_menu(chat_id)
