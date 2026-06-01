from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


def _int_env(env: Mapping[str, str], key: str, default: int) -> int:
    value = env.get(key)
    if value is None or value == "":
        return default
    return int(value)


def _float_env(env: Mapping[str, str], key: str, default: float) -> float:
    value = env.get(key)
    if value is None or value == "":
        return default
    return float(value)


def _bool_env(env: Mapping[str, str], key: str, default: bool) -> bool:
    value = env.get(key)
    if value is None or value == "":
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class AppConfig:
    port: int
    symbol_limit: int
    global_limit: int
    interval: str
    lookback_days: int
    min_history_days: int
    rolling_bars: int
    min_abs_pct_change: float
    min_volume_ratio: float
    scan_interval_seconds: int
    scan_workers: int
    fast_lane_enabled: bool
    fast_interval: str
    fast_lookback_days: int
    fast_rolling_bars: int
    fast_min_abs_pct_change: float
    fast_min_volume_ratio: float
    cooldown_seconds: int
    run_on_start: bool
    output_dir: Path
    state_path: Path
    telegram_bot_token: str | None
    telegram_chat_id: str | None

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        source = os.environ if env is None else env
        output_dir = Path(source.get("ANOMALY_OUTPUT_DIR", "outputs/live"))
        state_path = Path(source.get("ANOMALY_STATE_PATH", str(output_dir / "state.json")))
        chat_id = source.get("TELEGRAM_CHAT_ID") or source.get("TELEGRAM_USER_ID")
        return cls(
            port=_int_env(source, "PORT", 8080),
            symbol_limit=_int_env(source, "ANOMALY_SYMBOL_LIMIT", 150),
            global_limit=_int_env(source, "ANOMALY_GLOBAL_LIMIT", 10),
            interval=source.get("ANOMALY_INTERVAL", "4h"),
            lookback_days=_int_env(source, "ANOMALY_LOOKBACK_DAYS", 730),
            min_history_days=_int_env(source, "ANOMALY_MIN_HISTORY_DAYS", 180),
            rolling_bars=_int_env(source, "ANOMALY_ROLLING_BARS", 42),
            min_abs_pct_change=_float_env(source, "ANOMALY_MIN_ABS_PCT_CHANGE", 1.0),
            min_volume_ratio=_float_env(source, "ANOMALY_MIN_VOLUME_RATIO", 1.5),
            scan_interval_seconds=_int_env(source, "ANOMALY_SCAN_INTERVAL_SECONDS", 4 * 60 * 60),
            scan_workers=_int_env(source, "ANOMALY_SCAN_WORKERS", 8),
            fast_lane_enabled=_bool_env(source, "ANOMALY_FAST_LANE_ENABLED", True),
            fast_interval=source.get("ANOMALY_FAST_INTERVAL", "1h"),
            fast_lookback_days=_int_env(source, "ANOMALY_FAST_LOOKBACK_DAYS", 365),
            fast_rolling_bars=_int_env(source, "ANOMALY_FAST_ROLLING_BARS", 168),
            fast_min_abs_pct_change=_float_env(source, "ANOMALY_FAST_MIN_ABS_PCT_CHANGE", 1.0),
            fast_min_volume_ratio=_float_env(source, "ANOMALY_FAST_MIN_VOLUME_RATIO", 3.0),
            cooldown_seconds=_int_env(source, "ANOMALY_COOLDOWN_SECONDS", 12 * 60 * 60),
            run_on_start=_bool_env(source, "ANOMALY_RUN_ON_START", True),
            output_dir=output_dir,
            state_path=state_path,
            telegram_bot_token=source.get("TELEGRAM_BOT_TOKEN"),
            telegram_chat_id=chat_id,
        )
