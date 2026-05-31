from __future__ import annotations

import json
import urllib.request


def build_send_message_payload(chat_id: str, text: str) -> dict[str, str]:
    return {"chat_id": chat_id, "text": text}


def send_message(bot_token: str, chat_id: str, text: str) -> dict:
    payload = json.dumps(build_send_message_payload(chat_id, text)).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))
