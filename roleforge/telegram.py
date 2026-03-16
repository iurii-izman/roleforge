"""
Minimal Telegram Bot API client for MVP jobs.
"""

from __future__ import annotations

import json
import urllib.request
from typing import Any

from roleforge.runtime import TELEGRAM_SEND_MESSAGE_URL


def send_message(bot_token: str, chat_id: str, text: str) -> dict[str, Any]:
    payload = json.dumps({"chat_id": chat_id, "text": text}).encode("utf-8")
    request = urllib.request.Request(
        TELEGRAM_SEND_MESSAGE_URL.format(token=bot_token),
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request) as response:
        return json.loads(response.read().decode("utf-8"))
