"""
config.py — Centralised application configuration.
All environment variables are read ONCE here via python-dotenv.
Import `config` anywhere in the app — never call os.environ directly.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (one directory up from this file if needed,
# or same directory).  load_dotenv is safe to call multiple times.
_ENV_PATH = Path(__file__).parent / ".env"
load_dotenv(dotenv_path=_ENV_PATH, override=False)


class Config:
    # ── Flask ────────────────────────────────────────────────────────────────
    SECRET_KEY: str   = os.environ["SECRET_KEY"]
    FLASK_ENV: str    = os.getenv("FLASK_ENV", "production")
    PORT: int         = int(os.getenv("PORT", "5000"))
    DEBUG: bool       = FLASK_ENV == "development"

    # ── Admin credentials ────────────────────────────────────────────────────
    ADMIN_USER: str   = os.environ["ADMIN_USER"]
    ADMIN_PASS: str   = os.environ["ADMIN_PASS"]

    # ── Gemini ───────────────────────────────────────────────────────────────
    GEMINI_API_KEY: str   = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL: str     = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

    # ── Upload / render ──────────────────────────────────────────────────────
    MAX_UPLOAD_MB: int    = int(os.getenv("MAX_UPLOAD_MB", "100"))
    MAX_CONTENT_LENGTH: int = MAX_UPLOAD_MB * 1024 * 1024
    PDF_RENDER_DPI: int   = int(os.getenv("PDF_RENDER_DPI", "200"))
    ALLOWED_EXTENSIONS: frozenset = frozenset({"pdf"})

    # ── Paths ─────────────────────────────────────────────────────────────────
    BASE_DIR: Path    = Path(__file__).resolve().parent
    UPLOAD_DIR: Path  = BASE_DIR / "uploads"
    OUTPUT_DIR: Path  = BASE_DIR / "outputs"

    @classmethod
    def init_dirs(cls) -> None:
        cls.UPLOAD_DIR.mkdir(exist_ok=True)
        cls.OUTPUT_DIR.mkdir(exist_ok=True)


config = Config()
