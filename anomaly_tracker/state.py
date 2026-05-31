from __future__ import annotations

import json
from pathlib import Path

from anomaly_tracker.models import SignalCandidate


class CooldownState:
    def __init__(self, path: Path, cooldown_seconds: int, stronger_factor: float = 1.15):
        self.path = path
        self.cooldown_ms = cooldown_seconds * 1000
        self.stronger_factor = stronger_factor
        self._state = self._load()

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))

    def should_send(self, candidate: SignalCandidate) -> bool:
        previous = self._state.get(candidate.symbol)
        if not previous:
            return True
        elapsed = candidate.open_time - int(previous.get("last_open_time", 0))
        if elapsed >= self.cooldown_ms:
            return True
        previous_score = float(previous.get("last_score", 0.0))
        return candidate.score >= previous_score * self.stronger_factor

    def record_sent(self, candidate: SignalCandidate) -> None:
        self._state[candidate.symbol] = {
            "last_open_time": candidate.open_time,
            "last_score": candidate.score,
            "last_level": candidate.level,
            "last_direction": candidate.direction,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._state, indent=2), encoding="utf-8")
