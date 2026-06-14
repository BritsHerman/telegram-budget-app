import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.environ["TELEGRAM_TOKEN"]
SUPABASE_URL: str = os.environ["SUPABASE_URL"]
SUPABASE_SERVICE_KEY: str = os.environ["SUPABASE_SERVICE_KEY"]
