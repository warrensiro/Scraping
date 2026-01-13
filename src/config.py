import os
from dotenv import load_dotenv


ENV = os.getenv("ENV", "development").lower()

if ENV == "development":
    # Only load .env locally
    load_dotenv()


OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OXYLABS_USERNAME = os.getenv("OXYLABS_USERNAME")
OXYLABS_PASSWORD = os.getenv("OXYLABS_PASSWORD")


_missing = []

if not OPENAI_API_KEY:
    _missing.append("OPENAI_API_KEY")

if not OXYLABS_USERNAME:
    _missing.append("OXYLABS_USERNAME")

if not OXYLABS_PASSWORD:
    _missing.append("OXYLABS_PASSWORD")

if _missing:
    raise RuntimeError(
        "Missing required environment variables: "
        + ", ".join(_missing)
    )


OPENAI_MODEL_PRIMARY = os.getenv("OPENAI_MODEL_PRIMARY", "gpt-4o-mini")
OPENAI_MODEL_FALLBACK = os.getenv("OPENAI_MODEL_FALLBACK", "gpt-3.5-turbo")

MAX_COMPETITORS_FOR_LLM = int(os.getenv("MAX_COMPETITORS_FOR_LLM", "10"))
MAX_COMPETITOR_SCRAPE = int(os.getenv("MAX_COMPETITOR_SCRAPE", "20"))

REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", "30"))
