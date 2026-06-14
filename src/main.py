import src.handlers.callbacks  # noqa: F401 — registers all callback handlers
import src.handlers.replies  # noqa: F401 — registers reply handler
import src.handlers.start  # noqa: F401 — registers /start command
from src.bot_instance import bot
from src.db.client import get_client


def main() -> None:
    get_client()  # fail fast if Supabase credentials are wrong
    print("Bot polling started…")
    bot.infinity_polling(timeout=30, long_polling_timeout=15)


if __name__ == "__main__":
    main()
