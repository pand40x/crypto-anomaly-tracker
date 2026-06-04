from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


ALERT_MODES = {"instant", "digest", "critical_only"}
MIN_LEVELS = {"watch", "signal", "critical"}


@dataclass(frozen=True)
class WatchEntry:
    symbol: str
    tags: tuple[str, ...]
    alert_mode: str
    min_level: str
    added_at: str


def normalize_symbol(value: str) -> str:
    cleaned = value.strip().upper().replace("/", "")
    if cleaned.endswith("USDT"):
        return cleaned
    return f"{cleaned}USDT"


class WatchlistStore:
    def __init__(self, path: Path):
        self.path = path

    def _load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _save(self, payload: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def entries(self) -> list[WatchEntry]:
        payload = self._load()
        result: list[WatchEntry] = []
        for symbol, item in sorted(payload.items()):
            result.append(
                WatchEntry(
                    symbol=symbol,
                    tags=tuple(item.get("tags") or []),
                    alert_mode=str(item.get("alert_mode", "instant")),
                    min_level=str(item.get("min_level", "watch")),
                    added_at=str(item.get("added_at", "")),
                )
            )
        return result

    def symbols(self) -> list[str]:
        return [entry.symbol for entry in self.entries()]

    def get(self, symbol: str) -> WatchEntry | None:
        payload = self._load()
        item = payload.get(normalize_symbol(symbol))
        if item is None:
            return None
        return WatchEntry(
            symbol=normalize_symbol(symbol),
            tags=tuple(item.get("tags") or []),
            alert_mode=str(item.get("alert_mode", "instant")),
            min_level=str(item.get("min_level", "watch")),
            added_at=str(item.get("added_at", "")),
        )

    def add(self, symbol: str, tags: list[str] | None = None, alert_mode: str = "instant", min_level: str = "watch") -> WatchEntry:
        normalized = normalize_symbol(symbol)
        if alert_mode not in ALERT_MODES:
            raise ValueError(f"unsupported alert_mode: {alert_mode}")
        if min_level not in MIN_LEVELS:
            raise ValueError(f"unsupported min_level: {min_level}")
        payload = self._load()
        entry = {
            "tags": sorted({tag.strip().lower() for tag in (tags or []) if tag.strip()}),
            "alert_mode": alert_mode,
            "min_level": min_level,
            "added_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        payload[normalized] = entry
        self._save(payload)
        return WatchEntry(
            symbol=normalized,
            tags=tuple(entry["tags"]),
            alert_mode=alert_mode,
            min_level=min_level,
            added_at=entry["added_at"],
        )

    def remove(self, symbol: str) -> bool:
        normalized = normalize_symbol(symbol)
        payload = self._load()
        if normalized not in payload:
            return False
        del payload[normalized]
        self._save(payload)
        return True

    def set_mode(self, symbol: str, alert_mode: str) -> WatchEntry:
        normalized = normalize_symbol(symbol)
        payload = self._load()
        if normalized not in payload:
            raise KeyError(normalized)
        if alert_mode not in ALERT_MODES:
            raise ValueError(f"unsupported alert_mode: {alert_mode}")
        payload[normalized]["alert_mode"] = alert_mode
        self._save(payload)
        return self.get(normalized)  # type: ignore[return-value]

    def set_tags(self, symbol: str, tags: list[str]) -> WatchEntry:
        normalized = normalize_symbol(symbol)
        payload = self._load()
        if normalized not in payload:
            raise KeyError(normalized)
        payload[normalized]["tags"] = sorted({tag.strip().lower() for tag in tags if tag.strip()})
        self._save(payload)
        return self.get(normalized)  # type: ignore[return-value]


LEVEL_ORDER = {"watch": 0, "signal": 1, "critical": 2}


def watchlist_send_override(entry: WatchEntry | None, candidate_level: str, default_send: bool, default_reason: str) -> dict:
    if entry is None:
        return {"send": default_send, "reason": default_reason}
    if entry.alert_mode == "digest":
        return {"send": False, "reason": "watchlist_digest_mode"}
    if entry.alert_mode == "critical_only" and candidate_level != "critical":
        return {"send": False, "reason": "watchlist_critical_only"}
    if LEVEL_ORDER.get(candidate_level, -1) < LEVEL_ORDER.get(entry.min_level, 0):
        return {"send": False, "reason": "watchlist_below_min_level"}
    if not default_send and entry.alert_mode == "instant" and candidate_level in {"signal", "critical"}:
        return {"send": True, "reason": "watchlist_instant_override"}
    return {"send": default_send, "reason": default_reason}