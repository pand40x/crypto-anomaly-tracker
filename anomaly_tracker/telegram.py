from __future__ import annotations

import json
import urllib.request


def build_send_message_payload(chat_id: str, text: str) -> dict[str, str]:
    return {"chat_id": chat_id, "text": text}


def _api_request(bot_token: str, method: str, payload: dict | None = None, timeout: int = 30) -> dict:
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{bot_token}/{method}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def send_message(bot_token: str, chat_id: str, text: str) -> dict:
    return _api_request(bot_token, "sendMessage", build_send_message_payload(chat_id, text), timeout=30)


def get_updates(bot_token: str, offset: int | None = None, timeout_seconds: int = 25) -> list[dict]:
    payload: dict[str, object] = {
        "timeout": timeout_seconds,
        "allowed_updates": ["message"],
    }
    if offset is not None:
        payload["offset"] = offset
    response = _api_request(bot_token, "getUpdates", payload, timeout=timeout_seconds + 10)
    if not response.get("ok"):
        return []
    return list(response.get("result") or [])
