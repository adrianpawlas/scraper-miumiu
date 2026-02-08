"""Load settings from environment."""
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

BASE_URL = os.getenv("BASE_URL", "https://www.miumiu.com").rstrip("/")
# EU site embeds full product JSON in HTML; US loads it via JS. Default to EU for reliable scraping.
MARKET = os.getenv("MARKET", "en")
COUNTRY = os.getenv("COUNTRY", "eu")
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DRY_RUN = os.getenv("DRY_RUN", "0").strip().lower() in ("1", "true", "yes")
try:
    LIMIT = int(os.getenv("LIMIT", "0"))
except ValueError:
    LIMIT = 0

# Site path prefix, e.g. /us/en
SITE_PREFIX = f"/{COUNTRY}/{MARKET}"
