from telebot import types

from src.bot_instance import bot
from src.db.budgets import get_budget, get_all_budgets, set_budget
from src.db.categories import get_categories, get_category_by_id, remove_category
from src.db.transactions import delete_transaction, get_all_transactions_for_period
from src.db.users import resolve_user, set_budget_day
from src.handlers.menus import (
    cancel_markup,
    send_add_category_type_menu,
    send_main_menu,
    send_remove_category_type_menu,
    send_setup_menu,
    send_transactions_menu,
    show_categories_for_budget,
    show_categories_for_transaction,
    show_categories_to_remove,
    show_delete_transaction_menu,
)
from src.helpers import escape_v1, escape_v2, get_budget_period
from src.state import awaiting_reply
from src.visualization import generate_summary_charts


# ── Main menu ──────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("main_menu_"))
def cb_main_menu(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id
    mid = call.message.message_id

    if call.data == "main_menu_daily":
        send_transactions_menu(chat_id, mid)

    elif call.data == "main_menu_setup":
        send_setup_menu(chat_id, mid)

    elif call.data == "main_menu_help":
        _send_help(chat_id)

    elif call.data == "main_menu_summary":
        bot.edit_message_text("⏳ Generating your summary…", chat_id, mid)
        try:
            charts = generate_summary_charts(user["id"], user["budget_day"])
            for buf, caption in charts:
                bot.send_photo(chat_id, buf, caption=caption, parse_mode="Markdown")
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ Could not generate charts: {e}")
        send_main_menu(chat_id, "🔙 Back to the main menu:")


# ── Transactions ────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "show_expense_cats")
def cb_show_expense_cats(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    show_categories_for_transaction(call.message.chat.id, call.message.message_id, user["id"], "expense")


@bot.callback_query_handler(func=lambda c: c.data == "show_income_cats")
def cb_show_income_cats(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    show_categories_for_transaction(call.message.chat.id, call.message.message_id, user["id"], "income")


@bot.callback_query_handler(func=lambda c: c.data.startswith("add_tx_"))
def cb_add_tx(call):
    category_id = call.data.removeprefix("add_tx_")
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id

    cat = get_category_by_id(user["id"], category_id)
    if not cat:
        bot.send_message(chat_id, "⚠️ Category not found. It may have been deleted.")
        send_main_menu(chat_id)
        return

    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
    emoji = "💸" if cat["type"] == "expense" else "💰"
    prompt = bot.send_message(
        chat_id,
        f"{emoji} *Reply to this message* with the amount for *{escape_v1(cat['name'])}*:",
        parse_mode="Markdown",
        reply_markup=cancel_markup(),
    )
    awaiting_reply[chat_id] = {
        "action": "add_transaction",
        "category_id": category_id,
        "bot_prompt_message_id": prompt.message_id,
    }


# ── Transaction history ─────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "view_history")
def cb_view_history(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id

    start, end = get_budget_period(user["budget_day"])
    txns = get_all_transactions_for_period(user["id"], start, end)

    if not txns:
        bot.edit_message_text(
            "📋 No transactions recorded this period yet.",
            chat_id, call.message.message_id,
        )
        send_main_menu(chat_id)
        return

    expenses = [t for t in txns if t["type"] == "expense"]
    incomes  = [t for t in txns if t["type"] == "income"]

    lines = [f"📋 Transactions  {start.strftime('%d %b')} – {end.strftime('%d %b')}\n"]

    if expenses:
        lines.append("💸 EXPENSES")
        for t in expenses:
            date = t["transacted_at"][:10]
            lines.append(f"  • {t['categories']['name']}: R{float(t['amount']):.2f}  ({date})")
        lines.append(f"  Total: R{sum(float(t['amount']) for t in expenses):.2f}\n")

    if incomes:
        lines.append("💰 INCOME")
        for t in incomes:
            date = t["transacted_at"][:10]
            lines.append(f"  • {t['categories']['name']}: R{float(t['amount']):.2f}  ({date})")
        lines.append(f"  Total: R{sum(float(t['amount']) for t in incomes):.2f}\n")

    if expenses and incomes:
        net = sum(float(t["amount"]) for t in incomes) - sum(float(t["amount"]) for t in expenses)
        emoji = "✅" if net >= 0 else "⚠️"
        lines.append(f"{emoji} Net: R{net:+.2f}")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_daily"))
    bot.edit_message_text(
        "\n".join(lines), chat_id, call.message.message_id, reply_markup=markup
    )


# ── Setup — categories ──────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "add_cat_menu")
def cb_add_cat_menu(call):
    bot.answer_callback_query(call.id)
    send_add_category_type_menu(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("add_cat_type_"))
def cb_add_cat_type(call):
    category_type = call.data.removeprefix("add_cat_type_")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

    prompt = bot.send_message(
        chat_id,
        f"📝 *Reply to this message* with the name of the new {category_type} category:",
        parse_mode="Markdown",
        reply_markup=cancel_markup(),
    )
    awaiting_reply[chat_id] = {
        "action": "add_category",
        "category_type": category_type,
        "bot_prompt_message_id": prompt.message_id,
    }


@bot.callback_query_handler(func=lambda c: c.data == "remove_cat_menu")
def cb_remove_cat_menu(call):
    bot.answer_callback_query(call.id)
    send_remove_category_type_menu(call.message.chat.id, call.message.message_id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_cat_type_"))
def cb_remove_cat_type(call):
    category_type = call.data.removeprefix("remove_cat_type_")
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    show_categories_to_remove(call.message.chat.id, call.message.message_id, user["id"], category_type)


@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_cat_") and not c.data.startswith("remove_cat_type_"))
def cb_remove_cat(call):
    category_id = call.data.removeprefix("remove_cat_")
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id
    mid = call.message.message_id

    cat = get_category_by_id(user["id"], category_id)
    if not cat:
        bot.edit_message_text("⚠️ Category not found.", chat_id, mid)
        send_main_menu(chat_id)
        return

    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("✅ Yes, delete it", callback_data=f"confirm_remove_cat_{category_id}"),
        types.InlineKeyboardButton("❌ Keep it",        callback_data="back_to_setup"),
    )
    bot.edit_message_text(
        f"⚠️ Delete *{escape_v1(cat['name'])}*?\n\n"
        f"This will also remove its budget and cannot be undone.",
        chat_id, mid,
        parse_mode="Markdown",
        reply_markup=markup,
    )


@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_remove_cat_"))
def cb_confirm_remove_cat(call):
    category_id = call.data.removeprefix("confirm_remove_cat_")
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id

    cat = get_category_by_id(user["id"], category_id)
    remove_category(user["id"], category_id)

    name = cat["name"] if cat else "Category"
    bot.edit_message_text(
        f"✅ *{escape_v1(name)}* deleted.",
        chat_id, call.message.message_id,
        parse_mode="Markdown",
    )
    send_main_menu(chat_id)


@bot.callback_query_handler(func=lambda c: c.data == "view_cats")
def cb_view_cats(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id

    expense_cats = get_categories(user["id"], "expense")
    income_cats  = get_categories(user["id"], "income")
    budgets      = get_all_budgets(user["id"])

    lines = ["📋 *All categories:*\n"]
    lines.append("*Expenses*")
    lines += [f"• {escape_v2(c['name'])}" for c in expense_cats] or ["No categories\\."]
    lines.append("\n*Income*")
    lines += [f"• {escape_v2(c['name'])}" for c in income_cats] or ["No categories\\."]
    lines.append("\n*Budgets*")
    if budgets:
        lines += [
            f"• {escape_v2(b['categories']['name'])} \\({b['categories']['type']}\\): `R{float(b['amount']):.2f}`"
            for b in budgets
        ]
    else:
        lines.append("No budgets set\\.")

    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back", callback_data="back_to_setup"))
    bot.send_message(chat_id, "\n".join(lines), parse_mode="MarkdownV2", reply_markup=markup)


# ── Setup — delete transaction ──────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "delete_tx_menu")
def cb_delete_tx_menu(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    show_delete_transaction_menu(call.message.chat.id, call.message.message_id, user["id"])


@bot.callback_query_handler(func=lambda c: c.data.startswith("confirm_delete_"))
def cb_confirm_delete(call):
    tx_id = call.data.removeprefix("confirm_delete_")
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id

    success = delete_transaction(user["id"], tx_id)
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

    if success:
        bot.send_message(chat_id, "✅ Transaction deleted.")
    else:
        bot.send_message(chat_id, "⚠️ Could not delete that transaction (already gone?).")
    send_main_menu(chat_id)


# ── Setup — budgets ─────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "budget_amounts_menu")
def cb_budget_amounts_menu(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    show_categories_for_budget(call.message.chat.id, call.message.message_id, user["id"])


@bot.callback_query_handler(func=lambda c: c.data.startswith("budget_cat_"))
def cb_budget_cat(call):
    category_id = call.data.removeprefix("budget_cat_")
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id

    cat = get_category_by_id(user["id"], category_id)
    if not cat:
        bot.send_message(chat_id, "⚠️ Category not found.")
        send_main_menu(chat_id)
        return

    current = get_budget(user["id"], category_id)
    current_str = f"R{current:.2f}" if current is not None else "not set"

    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
    prompt = bot.send_message(
        chat_id,
        f"💰 *Reply to this message* with the budget for *{escape_v1(cat['name'])}*"
        f" (current: {escape_v1(current_str)}). Enter 0 to remove.",
        parse_mode="Markdown",
        reply_markup=cancel_markup(),
    )
    awaiting_reply[chat_id] = {
        "action": "set_budget",
        "category_id": category_id,
        "bot_prompt_message_id": prompt.message_id,
    }


# ── Setup — budget day ──────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "set_budget_day")
def cb_set_budget_day(call):
    bot.answer_callback_query(call.id)
    user = resolve_user(call.from_user)
    chat_id = call.message.chat.id

    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
    prompt = bot.send_message(
        chat_id,
        f"📅 *Reply to this message* with the day of the month (1–31) for your budget period "
        f"(current: {user['budget_day']}):",
        parse_mode="Markdown",
        reply_markup=cancel_markup(),
    )
    awaiting_reply[chat_id] = {
        "action": "set_budget_day",
        "bot_prompt_message_id": prompt.message_id,
    }


# ── Cancel prompt ───────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "cancel_prompt")
def cb_cancel_prompt(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    if chat_id in awaiting_reply:
        del awaiting_reply[chat_id]
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)
    send_main_menu(chat_id, "❌ Cancelled. Back to the main menu:")


# ── Navigation back buttons ─────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("back_to_"))
def cb_back(call):
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    mid = call.message.message_id

    if call.data == "back_to_main":
        send_main_menu(chat_id, "🔙 Back to the Main Menu:")
    elif call.data == "back_to_setup":
        send_setup_menu(chat_id, mid)
    elif call.data == "back_to_daily":
        send_transactions_menu(chat_id, mid)
    elif call.data == "back_to_remove_cat_type":
        send_remove_category_type_menu(chat_id, mid)


# ── No-op header buttons ────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data == "ignore_header")
def cb_ignore(call):
    bot.answer_callback_query(call.id)


# ── Help ─────────────────────────────────────────────────────────────────────

def _send_help(chat_id: int) -> None:
    text = (
        "❓ *How to use this bot*\n"
        "\n"
        "*🆕 First time setup*\n"
        "1\\. Go to ⚙️ Setup → Add Category and create your expense and income categories \\(e\\.g\\. Groceries, Salary\\)\n"
        "2\\. Go to Setup → Budget Amounts to set a monthly limit per category\n"
        "3\\. Optionally set your budget period start day \\(default is the 25th\\)\n"
        "\n"
        "*📅 Recording a transaction*\n"
        "1\\. Tap *Transactions* on the main menu\n"
        "2\\. Choose *Expense* or *Income*\n"
        "3\\. Tap the category\n"
        "4\\. The bot sends you a prompt — *reply directly to that message* with the amount \\(e\\.g\\. 250 or 49\\.99\\)\n"
        "5\\. Tap ❌ Cancel on the prompt if you change your mind\n"
        "\n"
        "*⚙️ Setup options*\n"
        "• *Add Category* — create a new expense or income label\n"
        "• *Remove Category* — delete a category \\(asks for confirmation first\\)\n"
        "• *View Categories* — see all your categories and current budgets\n"
        "• *Budget Amounts* — set or update a monthly budget for any category\n"
        "• *Set Budget Day* — choose which day of the month your period resets \\(default: 25\\)\n"
        "• *Delete Transaction* — shows your last 10 transactions as buttons, tap one to delete it\n"
        "\n"
        "*📋 History*\n"
        "Shows all transactions recorded in the current budget period, grouped by type with totals and a net position\\.\n"
        "\n"
        "*📊 Summary*\n"
        "Sends three charts:\n"
        "• Budget Tracker — spent vs remaining per category\n"
        "• Spending Breakdown — pie chart of where your money went\n"
        "• Net Position — total income vs total expenses with your net for the period\n"
        "\n"
        "*💡 Tips*\n"
        "• Each person who messages the bot gets their own private data\n"
        "• You must *reply to the bot's prompt message* when entering amounts\n"
        "• Enter 0 as a budget amount to remove the budget for that category\n"
        "• If you go over budget you'll see a warning when recording the transaction"
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main"))
    bot.send_message(chat_id, text, parse_mode="MarkdownV2", reply_markup=markup)
