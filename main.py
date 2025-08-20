import os
import telebot
from telebot import types
import sqlite3
import pandas as pd
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend to avoid threading issues
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from datetime import datetime, timedelta
import calendar

# --- Configuration and Bot Initialization ---

load_dotenv()
API_KEY = os.getenv("TELEGRAM_TOKEN")

if API_KEY is None:
    print("Error: TELEGRAM_TOKEN environment variable not set. Please set it in your .env file.")
    exit()

bot = telebot.TeleBot(API_KEY)

awaiting_transaction_reply = {}

# --- Helper Functions ---

def escape_markdown_v2(text):
    """Escapes characters that have special meaning in MarkdownV2."""
    special_chars = '_*[]()~`>#+-=|{}.!'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def escape_markdown_v1(text):
    """Escapes special characters for Telegram's MarkdownV1."""
    special_chars = '_*[`'
    for char in special_chars:
        text = text.replace(char, f'\\{char}')
    return text

def extract_command_text(message):
    """
    Extracts the text that comes after the bot command.
    Example: "/add My Category" -> "My Category"
    """
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        return parts[1].strip()
    return ""

def get_categories(file_name):
    """
    Reads categories from 'expense_categories.txt' or 'income_categories.txt' and returns them as a list.
    Handles FileNotFoundError gracefully.
    """
    try:
        with open(file_name, "r") as f:
            categories = [line.strip() for line in f if line.strip()]
        return categories
    except FileNotFoundError:
        return []

def get_budget_day():
    """Reads the budget day from budget_day.txt, defaults to 25 if not set."""
    try:
        with open("budget_day.txt", "r") as f:
            day = int(f.read().strip())
            if 1 <= day <= 31:
                return day
            else:
                return 25
    except (FileNotFoundError, ValueError):
        return 25

def set_budget_day(day):
    """Saves the budget day to budget_day.txt."""
    try:
        with open("budget_day.txt", "w") as f:
            f.write(str(day))
        return True
    except Exception as e:
        print(f"Error saving budget day: {e}")
        return False

def get_budget_period():
    """Returns the start and end dates of the current budget period in SAST."""
    budget_day = get_budget_day()
    today = datetime.now()  # Local time (SAST assumed)

    # Determine the current budget period
    if today.day < budget_day:
        # Period is from budget_day of last month to budget_day of this month
        end_date = today.replace(day=budget_day, hour=23, minute=59, second=59, microsecond=999999)
        start_date = (end_date - timedelta(days=calendar.monthrange(today.year, today.month - 1)[1])).replace(day=budget_day, hour=0, minute=0, second=0, microsecond=0)
        if start_date.month == 12:
            start_date = start_date.replace(year=start_date.year - 1)
    else:
        # Period is from budget_day of this month to budget_day of next month
        start_date = today.replace(day=budget_day, hour=0, minute=0, second=0, microsecond=0)
        end_date = (start_date + timedelta(days=calendar.monthrange(today.year, today.month)[1])).replace(day=budget_day, hour=23, minute=59, second=59, microsecond=999999)
        if end_date > today:
            end_date = today  # Don't include future dates

    print(f"DEBUG: Budget period - Start: {start_date}, End: {end_date}")
    return start_date, end_date

def get_spent_amount(category, transaction_type, start_date, end_date):
    """Calculates the total spent in a category within the budget period."""
    table = "expenses" if transaction_type == "expense" else "income"
    sql = f"""
    SELECT SUM(ammount) FROM {table}
    WHERE category = ? AND date >= ? AND date <= ?
    """
    start_date_str = start_date.strftime('%Y-%m-%d %H:%M:%S')
    end_date_str = end_date.strftime('%Y-%m-%d %H:%M:%S')
    result = execute_sql(sql, (category, start_date_str, end_date_str), fetchone=True)
    spent = result[0] if result and result[0] else 0.0
    print(f"DEBUG: get_spent_amount for {category} ({transaction_type}) from {start_date_str} to {end_date_str}: R{spent:.2f}")
    return spent

def execute_sql(sql, params=(), fetchone=False, fetchall=False):
    conn = sqlite3.connect("budget.db")
    cur = conn.cursor()
    cur.execute(sql, params)
    
    if fetchone:
        result = cur.fetchone()
        conn.close()
        return result
    elif fetchall:
        result = cur.fetchall()
        conn.close()
        return result
    else:
        # For INSERT, UPDATE, DELETE
        latest_id = cur.lastrowid
        conn.commit()
        conn.close()
        return latest_id

def setup_database():
    sql_expenses = """
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY NOT NULL,
        category TEXT,
        ammount REAL,
        date TEXT DEFAULT (datetime('now'))
    )
    """
    execute_sql(sql_expenses)

    sql_income = """
    CREATE TABLE IF NOT EXISTS income (
        id INTEGER PRIMARY KEY NOT NULL,
        category TEXT,
        ammount REAL,
        date TEXT DEFAULT (datetime('now'))
    )
    """
    execute_sql(sql_income)

    sql_budgets = """
    CREATE TABLE IF NOT EXISTS budgets (
        category TEXT PRIMARY KEY NOT NULL,
        amount REAL NOT NULL
    )
    """
    execute_sql(sql_budgets)

def add_transaction(transaction_type, category, ammount):
    transaction_id = None
    try:
        ammount = float(ammount)
        if transaction_type == 'expense':
            sql = "INSERT INTO expenses (category, ammount) VALUES (?, ?)"
        elif transaction_type == 'income':
            sql = "INSERT INTO income (category, ammount) VALUES (?, ?)"
        else:
            return None
        transaction_id = execute_sql(sql, (category, ammount))
        return transaction_id
    except ValueError:
        return transaction_id

def remove_expense(transaction_id):
    sql = "DELETE FROM expenses WHERE id = ?"
    try:
        execute_sql(sql, (transaction_id,))
        return True
    except:
        return False

def remove_income(transaction_id):
    sql = "DELETE FROM income WHERE id = ?"
    try:
        execute_sql(sql, (transaction_id,))
        return True
    except:
        return False

def remove_category(chat_id, category_to_remove, file):
    found = False
    updated_categories = []

    try:
        with open(file, "r") as f:
            for line in f:
                content = line.strip()
                if content == category_to_remove:
                    found = True
                else:
                    updated_categories.append(line)

        if found:
            with open(file, "w") as f:
                f.writelines(updated_categories)
            
            delete_budget(category_to_remove)

            reply_message = f"✅ Category **'{escape_markdown_v1(category_to_remove)}'** removed successfully."
        else:
            reply_message = f"⚠️ Category **'{escape_markdown_v1(category_to_remove)}'** not found in the list."

        reply_message += "\n\nAvailable categories:\n"
        categories_for_display = [escape_markdown_v1(item.strip()) for item in updated_categories if item.strip()]
        if categories_for_display:
            reply_message += "\n".join(categories_for_display)
        else:
            reply_message += "No categories available."
        
        bot.send_message(chat_id, reply_message, parse_mode='Markdown')

    except FileNotFoundError:
        bot.send_message(chat_id, "⚠️ The categories file was not found. There are no categories to remove yet.")
    except Exception as e:
        print(f"Error removing category '{category_to_remove}': {e}")
        bot.send_message(chat_id, "⚠️ An unexpected error occurred while trying to remove the category. Please try again later.")
    finally:
        send_main_menu(chat_id)

# --- Budget Functions ---
def set_budget(category, amount):
    """Inserts or updates a budget for a given category."""
    sql = """
    INSERT OR REPLACE INTO budgets (category, amount)
    VALUES (?, ?)
    """
    execute_sql(sql, (category, amount))

def get_budget(category):
    """Retrieves the budget for a specific category."""
    sql = "SELECT amount FROM budgets WHERE category = ?"
    result = execute_sql(sql, (category,), fetchone=True)
    return result[0] if result else None

def get_all_budgets():
    """Retrieves all stored budgets."""
    sql = "SELECT category, amount FROM budgets"
    return execute_sql(sql, fetchall=True)

def delete_budget(category):
    """Deletes a budget for a specific category."""
    sql = "DELETE FROM budgets WHERE category = ?"
    execute_sql(sql, (category,))

def visualize_budget():
    """Generates a stacked bar chart showing spending vs budget by category for the budget period."""
    start_date, end_date = get_budget_period()
    budget_day = get_budget_day()
    
    conn = sqlite3.connect("budget.db")
    expenses_df = pd.read_sql_query(
        "SELECT category, ammount FROM expenses WHERE date >= ? AND date <= ?",
        conn,
        params=(start_date.strftime('%Y-%m-%d %H:%M:%S'), end_date.strftime('%Y-%m-%d %H:%M:%S'))
    )
    budgets_df = pd.read_sql_query("SELECT category, amount FROM budgets WHERE category NOT LIKE 'income%'", conn)
    conn.close()

    print(f"DEBUG: Expenses retrieved: {len(expenses_df)} rows")
    if not expenses_df.empty:
        print(f"DEBUG: Sample expenses: {expenses_df.head().to_dict()}")

    expenses_df.columns = [col.strip().lower() for col in expenses_df.columns]
    budgets_df.columns = [col.strip().lower() for col in budgets_df.columns]

    spent_df = expenses_df.groupby("category")["ammount"].sum().reset_index()
    spent_df.rename(columns={"ammount": "spent"}, inplace=True)

    combined_df = pd.merge(budgets_df, spent_df, on="category", how="outer").fillna(0)
    combined_df["remaining"] = (combined_df["amount"] - combined_df["spent"]).clip(lower=0)

    spent_color = "orangered"
    remaining_color = "royalblue"

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.bar(combined_df["category"], combined_df["spent"], label="Spent", color=spent_color)
    ax.bar(combined_df["category"], combined_df["remaining"], bottom=combined_df["spent"], label="Remaining", color=remaining_color)

    for idx, row in combined_df.iterrows():
        ax.text(idx, row["spent"] / 2, f'{row["spent"]:.0f}', ha='center', va='center', color="white")
        ax.text(idx, row["spent"] + row["remaining"] / 2, f'{row["remaining"]:.0f}', ha='center', va='center', color="white")

    plt.title(f"Spending vs Budget (Period: {start_date.strftime('%d %b')} - {end_date.strftime('%d %b')})", fontsize=14)
    plt.ylabel("Amount")
    plt.xticks(rotation=90)
    plt.legend()
    plt.tight_layout()
    plt.savefig("budget_stack_chart.jpg", dpi=300)
    plt.close(fig)

# --- Message Handlers ---

def send_main_menu(chat_id, message_text="👋 Welcome! How can I help you today?"):
    markup = types.InlineKeyboardMarkup()
    daily_button = types.InlineKeyboardButton("📅 Transactions", callback_data="main_menu_daily")
    setup_button = types.InlineKeyboardButton("⚙️ Setup", callback_data="main_menu_setup")
    summary_button = types.InlineKeyboardButton("📊 Summary", callback_data="main_menu_summary")
    markup.add(daily_button, setup_button, summary_button)
    bot.send_message(chat_id, message_text, reply_markup=markup)

def send_daily_transactions_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    expense_button = types.InlineKeyboardButton("🔥 Expense", callback_data="show_expense_categories_from_menu")
    income_button = types.InlineKeyboardButton("🤑 Income", callback_data="show_income_categories_from_menu")
    back_button = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
    markup.add(expense_button, income_button, back_button)
    
    if message_id:
        bot.edit_message_text("📝 What would you like to record today?", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "📝 What would you like to record today?", reply_markup=markup)

def send_setup_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    add_cat_button = types.InlineKeyboardButton("➕ Add Category", callback_data="add_category_from_menu")
    remove_cat_button = types.InlineKeyboardButton("❌ Remove Category", callback_data="remove_category_from_menu")
    view_cat_button = types.InlineKeyboardButton("👀 View Categories", callback_data="view_categories_from_menu")
    delete_trans_button = types.InlineKeyboardButton("🗑️ Delete Transaction", callback_data="delete_transaction_from_menu")
    budget_amounts_button = types.InlineKeyboardButton("💰 Budget Amounts", callback_data="budget_amounts_from_menu")
    budget_day_button = types.InlineKeyboardButton("📅 Set Budget Day", callback_data="set_budget_day")
    back_button = types.InlineKeyboardButton("🔙 Back to Main Menu", callback_data="back_to_main")
    markup.add(add_cat_button, remove_cat_button, view_cat_button, delete_trans_button, budget_amounts_button, budget_day_button, back_button)

    if message_id:
        bot.edit_message_text("⚙️ Category and Transaction Management:", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "⚙️ Category and Transaction Management:", reply_markup=markup)

def send_add_category_type_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    expense_cat_button = types.InlineKeyboardButton("➖ Expense Category", callback_data="add_category_type_expense")
    income_cat_button = types.InlineKeyboardButton("➕ Income Category", callback_data="add_category_type_income")
    back_button = types.InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="back_to_setup")
    markup.add(expense_cat_button, income_cat_button, back_button)

    if message_id:
        bot.edit_message_text("📝 What type of category would you like to add?", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "📝 What type of category would you like to add?", reply_markup=markup)

def send_remove_category_type_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    expense_cat_button = types.InlineKeyboardButton("➖ Expense Category", callback_data="remove_category_type_expense")
    income_cat_button = types.InlineKeyboardButton("➕ Income Category", callback_data="remove_category_type_income")
    back_button = types.InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="back_to_setup")
    markup.add(expense_cat_button, income_cat_button, back_button)

    if message_id:
        bot.edit_message_text("📝 What type of category would you like to remove?", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "📝 What type of category would you like to remove?", reply_markup=markup)

def send_delete_transaction_type_menu(chat_id, message_id=None):
    markup = types.InlineKeyboardMarkup(row_width=2)
    expense_button = types.InlineKeyboardButton("➖ Delete Expense", callback_data="delete_type_expense")
    income_button = types.InlineKeyboardButton("➕ Delete Income", callback_data="delete_type_income")
    back_button = types.InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="back_to_setup")
    markup.add(expense_button, income_button, back_button)

    if message_id:
        bot.edit_message_text("📝 What type of transaction would you like to delete?", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "📝 What type of transaction would you like to delete?", reply_markup=markup)

def show_categories_for_expense_entry(chat_id, message_id=None):
    categories = get_categories("expense_categories.txt")
    markup = types.InlineKeyboardMarkup(row_width=2)

    if not categories:
        if message_id:
            bot.edit_message_text("⚠️ No expense categories available. Use Setup > Add Category to create some first!", chat_id, message_id, reply_markup=None)
        else:
            bot.send_message(chat_id, "⚠️ No expense categories available. Use Setup > Add Category to create some first!")
        send_daily_transactions_menu(chat_id, message_id=message_id)
        return

    for category in categories:
        button = types.InlineKeyboardButton(category, callback_data=f"add_expense_reply_{category}")
        markup.add(button)
    
    back_button = types.InlineKeyboardButton("🔙 Back to Transactions", callback_data="back_to_daily")
    markup.add(back_button)

    if message_id:
        bot.edit_message_text("📝 Select a category to add an expense:", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "📝 Select a category to add an expense:", reply_markup=markup)

def show_categories_for_income_entry(chat_id, message_id=None):
    categories = get_categories("income_categories.txt")
    markup = types.InlineKeyboardMarkup(row_width=2)

    if not categories:
        if message_id:
            bot.edit_message_text("⚠️ No income categories available. Use Setup > Add Category to create some first!", chat_id, message_id, reply_markup=None)
        else:
            bot.send_message(chat_id, "⚠️ No income categories available. Use Setup > Add Category to create some first!")
        send_daily_transactions_menu(chat_id, message_id=message_id)
        return

    for category in categories:
        button = types.InlineKeyboardButton(category, callback_data=f"add_income_reply_{category}")
        markup.add(button)
    
    back_button = types.InlineKeyboardButton("🔙 Back to Transactions", callback_data="back_to_daily")
    markup.add(back_button)

    if message_id:
        bot.edit_message_text("📝 Select a category to add income:", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "📝 Select a category to add income:", reply_markup=markup)

def show_categories_to_remove(chat_id, message_id, category_type):
    file_name = f"{category_type}_categories.txt"
    categories = get_categories(file_name)
    markup = types.InlineKeyboardMarkup(row_width=2)

    if not categories:
        bot.edit_message_text(f"⚠️ No {category_type} categories available to remove.", chat_id, message_id, reply_markup=None)
        send_remove_category_type_menu(chat_id, message_id)
        return

    for category in categories:
        button = types.InlineKeyboardButton(category, callback_data=f"remove_{category_type}_category_{category}")
        markup.add(button)
    
    back_button = types.InlineKeyboardButton(f"🔙 Back to Remove Category Type", callback_data="back_to_remove_category_type")
    markup.add(back_button)

    bot.edit_message_text(f"📝 Select a {category_type} category to remove:", chat_id, message_id, reply_markup=markup)

def show_categories_for_budget(chat_id, message_id=None):
    expense_categories = get_categories("expense_categories.txt")
    income_categories = get_categories("income_categories.txt")
    markup = types.InlineKeyboardMarkup(row_width=2)
    
    has_categories = False

    if expense_categories:
        markup.add(types.InlineKeyboardButton("--- Expense Categories ---", callback_data='ignore_header'))
        for category in expense_categories:
            callback_data_category = category.replace(' ', '~')
            button = types.InlineKeyboardButton(category, callback_data=f"set_budget_expense_{callback_data_category}")
            markup.add(button)
        has_categories = True

    if income_categories:
        markup.add(types.InlineKeyboardButton("--- Income Categories ---", callback_data='ignore_header'))
        for category in income_categories:
            callback_data_category = category.replace(' ', '~')
            button = types.InlineKeyboardButton(category, callback_data=f"set_budget_income_{callback_data_category}")
            markup.add(button)
        has_categories = True
    
    if not has_categories:
        if message_id:
            bot.edit_message_text("⚠️ No categories available to set a budget for. Use Setup > Add Category first!", chat_id, message_id, reply_markup=None)
        else:
            bot.send_message(chat_id, "⚠️ No categories available to set a budget for. Use Setup > Add Category first!")
        send_setup_menu(chat_id, message_id=message_id)
        return

    back_button = types.InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="back_to_setup")
    markup.add(back_button)

    if message_id:
        bot.edit_message_text("💰 Select a category to set or update its budget:", chat_id, message_id, reply_markup=markup)
    else:
        bot.send_message(chat_id, "💰 Select a category to set or update its budget:", reply_markup=markup)

@bot.message_handler(commands=["start"])
def send_welcome(message):
    send_main_menu(message.chat.id)

# --- Callback Query Handlers ---

@bot.callback_query_handler(func=lambda call: call.data.startswith('main_menu_'))
def callback_query_main_menu(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    bot.answer_callback_query(call.id)
    print(f"DEBUG: Main menu callback triggered: {call.data}")

    if call.data == 'main_menu_daily':
        send_daily_transactions_menu(chat_id, message_id)
    elif call.data == 'main_menu_setup':
        send_setup_menu(chat_id, message_id)
    elif call.data == 'main_menu_summary':
        visualize_budget()
        try:
            with open("budget_stack_chart.jpg", "rb") as photo:
                bot.send_photo(chat_id, photo, caption="📊 Here’s your spending summary!")
            os.remove("budget_stack_chart.jpg")
        except FileNotFoundError:
            bot.send_message(chat_id, "⚠️ Summary chart could not be generated. Please ensure you have data recorded.")
        except Exception as e:
            bot.send_message(chat_id, f"⚠️ An error occurred while sending the summary: {e}")
        # Send main menu as a new message
        send_main_menu(chat_id, message_text="🔙 Back to the main menu. How can I assist you further?")

@bot.callback_query_handler(func=lambda call: call.data == 'show_expense_categories_from_menu')
def handle_show_expense_categories_from_menu(call):
    print(f"DEBUG: Show expense categories triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    show_categories_for_expense_entry(chat_id, message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'show_income_categories_from_menu')
def handle_show_income_categories_from_menu(call):
    print(f"DEBUG: Show income categories triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    show_categories_for_income_entry(chat_id, message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'add_category_from_menu')
def handle_add_category_from_menu(call):
    print(f"DEBUG: Add category from menu triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    send_add_category_type_menu(chat_id, message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'remove_category_from_menu')
def handle_remove_category_from_menu(call):
    print(f"DEBUG: Remove category from menu triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    send_remove_category_type_menu(chat_id, message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'view_categories_from_menu')
def handle_view_categories_from_menu(call):
    print(f"DEBUG: View categories triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id

    reply = "📋 All available categories:\n\n"
    reply += "*Expenses*\n"
    expenses = get_categories("expense_categories.txt")
    if expenses:
        reply += "\n".join([f"\u2022 {escape_markdown_v2(exp)}" for exp in expenses]) + "\n"
    else:
        reply += "No categories added.\n"

    reply += "\n*Income*\n"
    incomes = get_categories("income_categories.txt")
    if incomes:
        reply += "\n".join([f"\u2022 {escape_markdown_v2(inc)}" for inc in incomes]) + "\n"
    else:
        reply += "No categories added.\n"
    
    reply += "\n*Budgets*\n"
    budgets = get_all_budgets()
    if budgets:
        reply += "\n".join([f"\u2022 {escape_markdown_v2(cat)}: `R{amt:.2f}`" for cat, amt in budgets]) + "\n"
    else:
        reply += "No budgets set.\n"

    markup = types.InlineKeyboardMarkup()
    back_button = types.InlineKeyboardButton("🔙 Back to Setup Menu", callback_data="back_to_setup")
    markup.add(back_button)

    bot.send_message(chat_id, reply, parse_mode='MarkdownV2', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: call.data == 'delete_transaction_from_menu')
def handle_delete_transaction_from_menu(call):
    print(f"DEBUG: Delete transaction from menu triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    send_delete_transaction_type_menu(chat_id, message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'budget_amounts_from_menu')
def handle_budget_amounts_from_menu(call):
    print(f"DEBUG: Budget amounts from menu triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    show_categories_for_budget(chat_id, message_id)

@bot.callback_query_handler(func=lambda call: call.data == 'set_budget_day')
def handle_set_budget_day(call):
    print(f"DEBUG: Set budget day triggered by chat {call.message.chat.id}")
    bot.answer_callback_query(call.id)
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

    current_day = get_budget_day()
    prompt_msg = bot.send_message(
        chat_id,
        f"📅 Please **reply to this message** with the day of the month (1-31) for your budget period start (current: {current_day}):",
        parse_mode='Markdown'
    )

    awaiting_transaction_reply[chat_id] = {
        'bot_prompt_message_id': prompt_msg.message_id,
        'action': 'set_budget_day'
    }
    print(f"DEBUG: User {chat_id} awaiting reply to message {prompt_msg.message_id} for setting budget day.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_category_type_'))
def callback_query_add_category_type(call):
    category_type = call.data.replace('add_category_type_', '')
    bot.answer_callback_query(call.id, f"Selected: Add {category_type.capitalize()} Category")
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

    prompt_msg = bot.send_message(
        chat_id, 
        f"📝 Please **reply to this message** with the name of the new {escape_markdown_v1(category_type)} category:",
        parse_mode='Markdown'
    )
    
    awaiting_transaction_reply[chat_id] = {
        'category_type_to_add': category_type,
        'bot_prompt_message_id': prompt_msg.message_id,
        'action': 'add_category'
    }
    print(f"DEBUG: User {chat_id} awaiting reply to message {prompt_msg.message_id} for adding {category_type} category.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_category_type_'))
def callback_query_remove_category_type(call):
    category_type = call.data.replace('remove_category_type_', '')
    bot.answer_callback_query(call.id, f"Selected: Remove {category_type.capitalize()} Category")
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    show_categories_to_remove(chat_id, message_id, category_type)

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_expense_reply_'))
def callback_query_add_expense_reply(call):
    category_name = call.data.removeprefix('add_expense_reply_')
    bot.answer_callback_query(call.id, f"Selected: {category_name}. Please enter amount now.")
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

    prompt_msg = bot.send_message(
        chat_id, 
        f"💸 Please **reply to this message** with the expense amount for '{escape_markdown_v1(category_name)}':",
        parse_mode='Markdown'
    )
    
    awaiting_transaction_reply[chat_id] = {
        'category': category_name,
        'bot_prompt_message_id': prompt_msg.message_id,
        'type': 'expense',
        'action': 'add'
    }
    print(f"DEBUG: User {chat_id} awaiting reply to message {prompt_msg.message_id} for expense category '{category_name}'.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_income_reply_'))
def callback_query_add_income_reply(call):
    category_name = call.data.removeprefix('add_income_reply_')
    bot.answer_callback_query(call.id, f"Selected: {category_name}. Please enter amount now.")
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

    prompt_msg = bot.send_message(
        chat_id, 
        f"💰 Please **reply to this message** with the income amount for '{escape_markdown_v1(category_name)}':",
        parse_mode='Markdown'
    )
    
    awaiting_transaction_reply[chat_id] = {
        'category': category_name,
        'bot_prompt_message_id': prompt_msg.message_id,
        'type': 'income',
        'action': 'add'
    }
    print(f"DEBUG: User {chat_id} awaiting reply to message {prompt_msg.message_id} for income category '{category_name}'.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('set_budget_'))
def callback_query_set_budget(call):
    data_suffix = call.data.removeprefix('set_budget_')
    parts = data_suffix.split('_', 1)

    if len(parts) < 2:
        bot.answer_callback_query(call.id, "⚠️ Invalid category selected. Please try again or report an issue.")
        send_setup_menu(call.message.chat.id, call.message.message_id)
        return

    budget_type = parts[0]
    encoded_category_name = parts[1]
    category_name = encoded_category_name.replace('~', ' ')

    print(f"DEBUG: Callback data: {call.data}")
    print(f"DEBUG: Parsed budget_type: {budget_type}, category_name: {category_name}")
    
    bot.answer_callback_query(call.id, f"Setting budget for: {category_name} ({budget_type.capitalize()})")
    
    chat_id = call.message.chat.id
    message_id = call.message.message_id

    bot.edit_message_reply_markup(chat_id=chat_id, message_id=message_id, reply_markup=None)

    current_budget = get_budget(category_name)
    budget_display = f"R{current_budget:.2f}" if current_budget is not None else "not set"

    escaped_category_name = escape_markdown_v1(category_name)
    escaped_budget_type = escape_markdown_v1(budget_type)
    escaped_budget_display = escape_markdown_v1(budget_display)

    prompt_msg = bot.send_message(
        chat_id,
        f"💰 Please **reply to this message** with the budget amount for '{escaped_category_name}' ({escaped_budget_type}):\n"
        f"*(Current budget: {escaped_budget_display})*",
        parse_mode='Markdown'
    )

    awaiting_transaction_reply[chat_id] = {
        'category': category_name,
        'bot_prompt_message_id': prompt_msg.message_id,
        'action': 'set_budget'
    }

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_expense_category_'))
def callback_query_remove_expense_category(call):
    category_name = call.data.removeprefix('remove_expense_category_')
    bot.answer_callback_query(call.id, f"Attempting to remove: {category_name}")
    chat_id = call.message.chat.id
    remove_category(chat_id, category_name, "expense_categories.txt")
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('remove_income_category_'))
def callback_query_remove_income_category(call):
    category_name = call.data.removeprefix('remove_income_category_')
    bot.answer_callback_query(call.id, f"Attempting to remove: {category_name}")
    chat_id = call.message.chat.id
    remove_category(chat_id, category_name, "income_categories.txt")
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_type_'))
def callback_query_delete_type(call):
    transaction_type_to_delete = call.data.removeprefix('delete_type_')
    bot.answer_callback_query(call.id, f"Selected: Delete {transaction_type_to_delete.capitalize()}")
    chat_id = call.message.chat.id
    bot.edit_message_reply_markup(chat_id=chat_id, message_id=call.message.message_id, reply_markup=None)

    prompt_msg = bot.send_message(
        chat_id, 
        f"🗑️ Please **reply to this message** with the ID of the {escape_markdown_v1(transaction_type_to_delete)} to delete:",
        parse_mode='Markdown'
    )
    
    awaiting_transaction_reply[chat_id] = {
        'type_to_delete': transaction_type_to_delete,
        'bot_prompt_message_id': prompt_msg.message_id,
        'action': 'delete'
    }
    print(f"DEBUG: User {chat_id} awaiting reply to message {prompt_msg.message_id} for deleting {transaction_type_to_delete}.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('back_to_'))
def callback_query_back_button(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    bot.answer_callback_query(call.id)
    print(f"DEBUG: Back button triggered: {call.data}")

    if call.data == 'back_to_main':
        send_main_menu(chat_id, message_text="🔙 Back to the Main Menu:")
    elif call.data == 'back_to_setup':
        send_setup_menu(chat_id, message_id)
    elif call.data == 'back_to_daily':
        send_daily_transactions_menu(chat_id, message_id)
    elif call.data == 'back_to_remove_category_type':
        send_remove_category_type_menu(chat_id, message_id)
    elif call.data == 'back_to_budget_menu':
        send_setup_menu(chat_id, message_id)

@bot.message_handler(func=lambda message: message.reply_to_message and \
                                         message.reply_to_message.from_user.id == bot.get_me().id and \
                                         message.chat.id in awaiting_transaction_reply and \
                                         message.reply_to_message.message_id == awaiting_transaction_reply[message.chat.id]['bot_prompt_message_id'] and \
                                         message.content_type == 'text')
def process_transaction_reply(message):
    chat_id = message.chat.id
    print(f"DEBUG: process_transaction_reply received message: '{message.text}' from chat {chat_id}. Is reply to bot: {message.reply_to_message.message_id}")

    stored_info = awaiting_transaction_reply.get(chat_id)
    if not stored_info:
        bot.send_message(chat_id, "⚠️ Context lost. Please start over using /start.")
        return

    action = stored_info.get('action')

    if action == 'add':
        selected_category = stored_info['category']
        transaction_type = stored_info['type']
        amount_str = message.text.strip()

        try:
            amount = float(amount_str)
            if amount <= 0:
                raise ValueError("Amount must be positive.")

            # Save the transaction first
            transaction_id = add_transaction(transaction_type, selected_category, amount)
            
            if transaction_id:
                transaction_word = "expense" if transaction_type == 'expense' else "income"
                # Get budget and spent amounts (after saving transaction)
                budget = get_budget(selected_category)
                start_date, end_date = get_budget_period()
                spent = get_spent_amount(selected_category, transaction_type, start_date, end_date)
                budget_display = f"R{budget:.2f}" if budget is not None else "not set"
                message = (
                    f"✅ Recorded R{amount:.2f} for {transaction_word} category '{escape_markdown_v1(selected_category)}' (ID: {transaction_id}).\n"
                    f"💰 Budget: {budget_display}\n"
                    f"📈 Spent this period: R{spent:.2f}"
                )
                bot.send_message(chat_id, message, parse_mode='Markdown')
            else:
                bot.send_message(chat_id, "⚠️ A database error has occurred, please try recording the transaction later.")
            
            del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} successfully added {transaction_type} for '{selected_category}'. Cleared entry.")
            send_main_menu(chat_id)

        except ValueError:
            bot.send_message(chat_id, "⚠️ That doesn't look like a valid amount. Please enter a positive number (e.g., 50.00 or 123). **Reply to the original prompt message again.**")
            print(f"DEBUG: User {chat_id} provided invalid amount. Re-prompting.")
        except Exception as e:
            print(f"Error processing {transaction_type} amount for chat {chat_id}: {e}")
            bot.send_message(chat_id, "⚠️ An unexpected error occurred while saving your transaction. Please try again.")
            if chat_id in awaiting_transaction_reply:
                del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} encountered unexpected error. Cleared entry.")
            send_main_menu(chat_id)

    elif action == 'delete':
        type_to_delete = stored_info['type_to_delete']
        transaction_id_str = message.text.strip()

        try:
            transaction_id = int(transaction_id_str)
            if transaction_id <= 0:
                raise ValueError("ID must be a positive integer.")

            if type_to_delete == 'expense':
                success = remove_expense(transaction_id)
                table_name = "expense"
            elif type_to_delete == 'income':
                success = remove_income(transaction_id)
                table_name = "income"
            else:
                bot.send_message(chat_id, "⚠️ Invalid transaction type for deletion. Please try again.")
                del awaiting_transaction_reply[chat_id]
                send_main_menu(chat_id)
                return

            if success:
                bot.send_message(chat_id, f"✅ {table_name.capitalize()} with ID {transaction_id} deleted successfully.")
            else:
                bot.send_message(chat_id, f"⚠️ Could not delete {table_name} with ID {transaction_id}. It might not exist or an error occurred.")
            
            del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} successfully processed delete for {type_to_delete} ID {transaction_id}. Cleared entry.")
            send_main_menu(chat_id)

        except ValueError:
            bot.send_message(chat_id, "⚠️ That doesn't look like a valid ID. Please enter a positive integer (e.g., 1, 5, 10). **Reply to the original prompt message again.**")
            print(f"DEBUG: User {chat_id} provided invalid ID. Re-prompting for delete.")
        except Exception as e:
            print(f"Error processing delete ID for chat {chat_id}: {e}")
            bot.send_message(chat_id, "⚠️ An unexpected error occurred while deleting your transaction. Please try again.")
            if chat_id in awaiting_transaction_reply:
                del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} encountered unexpected error during delete. Cleared entry.")
            send_main_menu(chat_id)

    elif action == 'add_category':
        category_type_to_add = stored_info['category_type_to_add']
        new_category_name = message.text.strip()
        file_name = f"{category_type_to_add}_categories.txt"

        if not new_category_name:
            bot.send_message(chat_id, "⚠️ Category name cannot be empty. Please **reply to the original prompt message again** with a valid name.")
            return

        if category_type_to_add == 'income' and not new_category_name.lower().startswith('income '):
            new_category_name = "income " + new_category_name

        existing_categories = get_categories(file_name)
        if new_category_name in existing_categories:
            bot.send_message(chat_id, f"⚠️ Category '{escape_markdown_v1(new_category_name)}' already exists in {category_type_to_add} categories. Please choose a different name or **reply to the original prompt message again**.")
            return

        try:
            with open(file_name, "a") as f:
                f.write(new_category_name + "\n")
            
            reply_text = f"✅ Category '{escape_markdown_v1(new_category_name)}' added successfully to {category_type_to_add} categories."
            bot.send_message(chat_id, reply_text)
            del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} successfully added new {category_type_to_add} category '{new_category_name}'. Cleared entry.")
            send_main_menu(chat_id)

        except Exception as e:
            print(f"Error adding {category_type_to_add} category '{new_category_name}': {e}")
            bot.send_message(chat_id, "⚠️ An unexpected error occurred while adding the category. Please try again later.")
            if chat_id in awaiting_transaction_reply:
                del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} encountered unexpected error during add_category. Cleared entry.")
            send_main_menu(chat_id)

    elif action == 'set_budget':
        selected_category = stored_info['category']
        amount_str = message.text.strip()

        try:
            amount = float(amount_str)
            if amount < 0:
                raise ValueError("Budget amount cannot be negative.")
            
            set_budget(selected_category, amount)
            
            if amount == 0:
                bot.send_message(chat_id, f"✅ Budget for '{escape_markdown_v1(selected_category)}' removed.")
            else:
                bot.send_message(chat_id, f"✅ Budget for '{escape_markdown_v1(selected_category)}' set to R{amount:.2f}.")
            
            del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} successfully set budget for '{selected_category}'. Cleared entry.")
            send_main_menu(chat_id)

        except ValueError:
            bot.send_message(chat_id, "⚠️ That doesn't look like a valid budget amount. Please enter a positive number (e.g., 1000.00 or 500). Enter 0 to remove the budget. **Reply to the original prompt message again.**")
            print(f"DEBUG: User {chat_id} provided invalid budget amount. Re-prompting.")
        except Exception as e:
            print(f"Error setting budget for chat {chat_id}: {e}")
            bot.send_message(chat_id, "⚠️ An unexpected error occurred while setting your budget. Please try again.")
            if chat_id in awaiting_transaction_reply:
                del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} encountered unexpected error during set_budget. Cleared entry.")
            send_main_menu(chat_id)

    elif action == 'set_budget_day':
        day_str = message.text.strip()

        try:
            day = int(day_str)
            if not 1 <= day <= 31:
                raise ValueError("Day must be between 1 and 31.")
            
            if set_budget_day(day):
                bot.send_message(chat_id, f"✅ Budget period start day set to {day}.")
            else:
                bot.send_message(chat_id, "⚠️ Failed to save budget day. Please try again.")
            
            del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} successfully set budget day to {day}. Cleared entry.")
            send_main_menu(chat_id)

        except ValueError:
            bot.send_message(chat_id, "⚠️ That doesn't look like a valid day. Please enter a number between 1 and 31. **Reply to the original prompt message again.**")
            print(f"DEBUG: User {chat_id} provided invalid budget day. Re-prompting.")
        except Exception as e:
            print(f"Error setting budget day for chat {chat_id}: {e}")
            bot.send_message(chat_id, "⚠️ An unexpected error occurred while setting the budget day. Please try again.")
            if chat_id in awaiting_transaction_reply:
                del awaiting_transaction_reply[chat_id]
            print(f"DEBUG: User {chat_id} encountered unexpected error during set_budget_day. Cleared entry.")
            send_main_menu(chat_id)

# --- Main function and Bot Polling ---
def main():
    try:
        print("Bot polling started...")
        setup_database()
        bot.polling(none_stop=True, interval=3, timeout=30)
        print("Bot polling stopped.")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        import traceback
        traceback.print_exc()
        print("Bot encountered an error and stopped. Relying on external process manager for restart.")

if __name__ == "__main__":
    main()