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
    PDF_RENDER_DPI: int   = int(os.getenv("PDF_RENDER_DPI", "300"))
    ALLOWED_EXTENSIONS: frozenset = frozenset({"pdf"})

    # ── MySQL (cl_module, cl_topic — database: cl_json_schema) ─────────────────
    MYSQL_HOST: str     = os.getenv("MYSQL_HOST", "localhost")
    MYSQL_PORT: int     = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_DATABASE: str = os.getenv("MYSQL_DATABASE", "cl_json_schema")
    MYSQL_USER: str     = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD: str = os.getenv("MYSQL_PASSWORD", "")

    # ── LDAP ─────────────────────────────────────────────────────────────────
    LDAP_ENABLED: bool  = os.getenv("LDAP_ENABLED", "false").lower() == "true"
    LDAP_HOST: str      = os.getenv("LDAP_HOST", "")
    LDAP_PORT: int      = int(os.getenv("LDAP_PORT", "389"))
    LDAP_USE_SSL: bool  = os.getenv("LDAP_USE_SSL", "false").lower() == "true"
    LDAP_BIND_DN: str   = os.getenv("LDAP_BIND_DN", "")   # service-account DN for user lookup
    LDAP_BIND_PASS: str = os.getenv("LDAP_BIND_PASS", "")
    LDAP_BASE_DN: str   = os.getenv("LDAP_BASE_DN", "")   # e.g. dc=example,dc=com
    LDAP_USER_FILTER: str = os.getenv("LDAP_USER_FILTER", "(sAMAccountName={username})")  # AD default

    # ── AWS / S3 ─────────────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str     = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str            = os.getenv("AWS_REGION", "us-east-1")
    S3_BUCKET: str             = os.getenv("S3_BUCKET", "")

    @property
    def s3_configured(self) -> bool:
        return bool(self.AWS_ACCESS_KEY_ID and self.AWS_SECRET_ACCESS_KEY and self.S3_BUCKET)

    # ── Paths ─────────────────────────────────────────────────────────────────
    BASE_DIR: Path    = Path(__file__).resolve().parent
    UPLOAD_DIR: Path  = BASE_DIR / "uploads"
    OUTPUT_DIR: Path  = BASE_DIR / "outputs"

    @classmethod
    def init_dirs(cls) -> None:
        cls.UPLOAD_DIR.mkdir(exist_ok=True)
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "modules").mkdir(exist_ok=True)
        (cls.OUTPUT_DIR / "topics").mkdir(exist_ok=True)


config = Config()
