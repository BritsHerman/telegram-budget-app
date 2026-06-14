# telegram-budget-app
An intuitive budget app built on Python, using Supabase (PostgreSQL) for all data storage and an easy-to-navigate Telegram interface consisting of buttons to create and delete categories, record transactions, and track budgets. Each Telegram user gets their own fully isolated data — great for shared use between multiple people.

## Tech stack
- **Python 3.12** with [pyTelegramBotAPI](https://github.com/eternnoir/pyTelegramBotAPI)
- **Supabase** (PostgreSQL) — transactions, categories, budgets, per-user settings
- **Docker** — single container, ready to deploy anywhere
- **matplotlib + pandas** — spending vs budget chart

## How do I use it?

### 1. Set up Supabase
1. Create a free project at [supabase.com](https://supabase.com)
2. Open **SQL Editor** and run the contents of [`supabase_setup.sql`](supabase_setup.sql) — this creates all the tables, indexes, and RLS policies in one shot
3. Copy your **Project URL** and **service_role key** from Project Settings → API

### 2. Configure environment variables
Copy `.env.example` to `.env` and fill in your three values:
```
TELEGRAM_TOKEN=your_telegram_bot_token_here
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key_here
```
Get your Telegram token from [@BotFather](https://t.me/botfather).

### 3. Run it
**With Docker (recommended):**
```bash
docker compose up -d
```

**Without Docker:**
```bash
pip install -r requirements.txt
python -m src.main
```

That's it. No manual database setup — the SQL file handles everything. Start the bot by sending it `/start`.

## Hosting
Works great on any Docker-capable host. I use **AWS with EasyPanel** — point it at this repo, set the three environment variables, and deploy. Previously ran on a Raspberry Pi 3B+ without issues too.

## How is the data stored?
Everything lives in Supabase (PostgreSQL):

| Table | What's in it |
|---|---|
| `users` | One row per Telegram user, including their personal `budget_day` |
| `categories` | Expense and income categories, per user |
| `budgets` | Monthly budget amounts per category, per user |
| `transactions` | All recorded expenses and income |

Row Level Security (RLS) is enabled — users can only ever see and edit their own data.

## How can I see what's going on?
Tap the **Summary** button for a quick bar chart showing how much you've spent vs your budget for each category since the last budget start day.

## Why use it?
With an intuitive and easy-to-use interface, recording transactions is much simpler — rather than having a budget app try to record transactions and categorize them wrong, OR having to open a spreadsheet that you'll fall behind on after a week and then frantically go through your bank statements to catch up.

## Great for analysis
Export your data as CSV from the Supabase dashboard and import it into any reporting tool — Excel, Power BI, Looker Studio. Build out your own visualizations. Do what works for you.

## User interface

Start the bot with `/start`:

<img width="613" height="177" alt="image" src="https://github.com/user-attachments/assets/0d38e51f-fab0-4714-8c54-a0f89b756ee6" />

Click **Setup** for category and budget management:

<img width="594" height="298" alt="image" src="https://github.com/user-attachments/assets/18b9f2ad-6258-43e0-80b0-5d78916c80ca" />

Click **Transactions** to record an expense or income:

<img width="608" height="206" alt="image" src="https://github.com/user-attachments/assets/a36b38fd-9438-460e-8ea2-5cd442e20f5d" />

Click **Summary** to see where you're at (blurred for privacy):

<img width="558" height="455" alt="image" src="https://github.com/user-attachments/assets/d84549f1-602e-47bd-b6ec-066d8db22247" />
