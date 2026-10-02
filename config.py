"""Central configuration. Values come from environment variables or the .env file."""
import os
import secrets
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def _bool(name: str, default: bool = False) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


# ---------------------------------------------------------------- Gemini
GEMINI_API_KEY = (os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY") or "").strip()
if GEMINI_API_KEY.lower().startswith("your_"):  # untouched placeholder from .env.example
    GEMINI_API_KEY = ""

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash").strip()
GEMINI_FALLBACK_MODELS = [
    m.strip()
    for m in os.getenv("GEMINI_FALLBACK_MODELS", "gemini-flash-latest,gemini-3.8-flash").split(",")
    if m.strip()
]
GEMINI_TIMEOUT_SECONDS = _int("GEMINI_TIMEOUT_SECONDS", 90)

# ---------------------------------------------------------------- Security
SECRET_KEY = os.getenv("SECRET_KEY", "").strip()
SECRET_KEY_IS_EPHEMERAL = not SECRET_KEY
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)  # logins reset on every restart unless SECRET_KEY is set
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = _int("ACCESS_TOKEN_EXPIRE_MINUTES", 60)
SESSION_IDLE_MINUTES = 30
COOKIE_SECURE = _bool("COOKIE_SECURE", False)  # set true when served over HTTPS
CORS_ORIGINS = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000").split(",")
    if o.strip()
]

# ---------------------------------------------------------------- Storage
DB_PATH = Path(os.getenv("DB_PATH") or BASE_DIR / "pocketsmart.db")
UPLOAD_DIR = BASE_DIR / "static" / "uploads"
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
KEEP_UPLOADS = _bool("KEEP_UPLOADS", False)  # outfit photos are deleted after analysis by default

# ---------------------------------------------------------------- Server
HOST = os.getenv("HOST", "127.0.0.1")
PORT = _int("PORT", 8000)
