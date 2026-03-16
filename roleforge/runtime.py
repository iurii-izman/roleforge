"""
Runtime helpers for local MVP execution.

Loads settings from process env first, then an optional .env file, then the
roleforge keyring for secrets that have a documented mapping.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

import psycopg2
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build


REPO_ROOT = Path(__file__).resolve().parent.parent
KEYRING_SCRIPT = REPO_ROOT / "scripts" / "roleforge-keyring.sh"
DOTENV_PATH = REPO_ROOT / ".env"
GMAIL_READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
TELEGRAM_SEND_MESSAGE_URL = "https://api.telegram.org/bot{token}/sendMessage"

_DOTENV_CACHE: dict[str, str] | None = None
_ENV_TO_KEYRING: dict[str, tuple[str, str]] = {
    "DATABASE_URL": ("db", "url"),
    "GMAIL_CLIENT_ID": ("google", "client_id"),
    "GMAIL_CLIENT_SECRET": ("google", "client_secret"),
    "GMAIL_REFRESH_TOKEN": ("google", "refresh_token"),
    "TELEGRAM_BOT_TOKEN": ("telegram", "bot_token"),
    "OPENAI_API_KEY": ("openai", "api_key"),
    "ANTHROPIC_API_KEY": ("anthropic", "api_key"),
    "LINEAR_API_KEY": ("linear", "api_key"),
}


def _parse_dotenv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(("'", '"')) and value.endswith(("'", '"')) and len(value) >= 2:
            value = value[1:-1]
        if " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        out[key] = value
    return out


def dotenv_values() -> dict[str, str]:
    global _DOTENV_CACHE
    if _DOTENV_CACHE is None:
        _DOTENV_CACHE = _parse_dotenv(DOTENV_PATH)
    return _DOTENV_CACHE


def get_setting(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value not in (None, ""):
        return value
    value = dotenv_values().get(name)
    if value not in (None, ""):
        return value
    mapping = _ENV_TO_KEYRING.get(name)
    if mapping:
        keyring_value = get_keyring_secret(*mapping)
        if keyring_value not in (None, ""):
            return keyring_value
    return default


def require_setting(name: str) -> str:
    value = get_setting(name)
    if value in (None, ""):
        raise RuntimeError(f"Missing required setting: {name}")
    return value


def get_keyring_secret(domain: str, key: str) -> str | None:
    if not KEYRING_SCRIPT.exists():
        return None
    result = subprocess.run(
        [str(KEYRING_SCRIPT), "get", domain, key],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    value = result.stdout.strip()
    return value or None


def connect_db() -> Any:
    return psycopg2.connect(require_setting("DATABASE_URL"))


def build_gmail_service() -> Any:
    credentials = Credentials(
        token=None,
        refresh_token=require_setting("GMAIL_REFRESH_TOKEN"),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=require_setting("GMAIL_CLIENT_ID"),
        client_secret=require_setting("GMAIL_CLIENT_SECRET"),
        scopes=[GMAIL_READONLY_SCOPE],
    )
    credentials.refresh(Request())
    return build("gmail", "v1", credentials=credentials, cache_discovery=False)


def load_jsonb(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        return json.loads(value)
    return dict(value)
