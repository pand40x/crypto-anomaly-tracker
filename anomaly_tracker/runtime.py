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
    market_filter_enabled: bool
    market_reference_symbol: str
    market_reference_symbols: tuple[str, ...]
    market_risk_off_pct_change: float
    market_risk_on_pct_change: float
    telegram_commands_enabled: bool
    telegram_poll_timeout_seconds: int
    public_base_url: str | None
    scan_secret: str | None
    watch_pct: float
    signal_pct: float
    critical_pct: float
    confirmation_bonus: float
    watchlist_path: Path
    watchlist_min_pct_factor: float
    sector_min_count: int
    sector_min_avg_score: float
    sector_alert_min_count: int

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "AppConfig":
        source = os.environ if env is None else env
        output_dir = Path(source.get("ANOMALY_OUTPUT_DIR", "outputs/live"))
        state_path = Path(source.get("ANOMALY_STATE_PATH", str(output_dir / "state.json")))
        chat_id = source.get("TELEGRAM_CHAT_ID") or source.get("TELEGRAM_USER_ID")
        secondary = source.get("ANOMALY_MARKET_SECONDARY_SYMBOL", "ETHUSDT").strip()
        references = [source.get("ANOMALY_MARKET_REFERENCE_SYMBOL", "BTCUSDT").strip()]
        if secondary and secondary not in references:
            references.append(secondary)
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
            market_filter_enabled=_bool_env(source, "ANOMALY_MARKET_FILTER_ENABLED", True),
            market_reference_symbol=references[0],
            market_reference_symbols=tuple(references),
            market_risk_off_pct_change=_float_env(source, "ANOMALY_MARKET_RISK_OFF_PCT_CHANGE", -2.5),
            market_risk_on_pct_change=_float_env(source, "ANOMALY_MARKET_RISK_ON_PCT_CHANGE", 2.5),
            telegram_commands_enabled=_bool_env(source, "TELEGRAM_COMMANDS_ENABLED", True),
            telegram_poll_timeout_seconds=_int_env(source, "TELEGRAM_POLL_TIMEOUT_SECONDS", 25),
            public_base_url=source.get("ANOMALY_PUBLIC_BASE_URL") or None,
            scan_secret=source.get("ANOMALY_SCAN_SECRET") or None,
            watch_pct=_float_env(source, "ANOMALY_WATCH_PCT", 0.95),
            signal_pct=_float_env(source, "ANOMALY_SIGNAL_PCT", 0.985),
            critical_pct=_float_env(source, "ANOMALY_CRITICAL_PCT", 0.995),
            confirmation_bonus=_float_env(source, "ANOMALY_CONFIRMATION_BONUS", 0.8),
            watchlist_path=Path(source.get("ANOMALY_WATCHLIST_PATH", str(output_dir / "watchlist.json"))),
            watchlist_min_pct_factor=_float_env(source, "ANOMALY_WATCHLIST_MIN_PCT_FACTOR", 0.5),
            sector_min_count=_int_env(source, "ANOMALY_SECTOR_MIN_COUNT", 3),
            sector_min_avg_score=_float_env(source, "ANOMALY_SECTOR_MIN_AVG_SCORE", 2.0),
            sector_alert_min_count=_int_env(source, "ANOMALY_SECTOR_ALERT_MIN_COUNT", 3),
        )
