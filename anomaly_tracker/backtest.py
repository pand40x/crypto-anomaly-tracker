from __future__ import annotations

from anomaly_tracker.binance import BinanceClient
from anomaly_tracker.scoring import calibrate_asset


def run_backtest(
    symbols: list[str],
    interval: str = "4h",
    lookback_days: int = 180,
    rolling_bars: int = 42,
    forward_bars: int = 6,
    min_history_days: int = 90,
) -> dict:
    client = BinanceClient()
    end_ms = client.server_time_ms()
    start_ms = end_ms - lookback_days * 24 * 60 * 60 * 1000
    candles_per_day = 6 if interval == "4h" else 24 if interval == "1h" else 1
    min_candles = max(rolling_bars + 10, min_history_days * candles_per_day)

    events: list[dict] = []
    for symbol in symbols:
        candles = client.klines(symbol, interval, start_ms, end_ms)
        if len(candles) < min_candles:
            continue
        calibration = calibrate_asset(symbol, candles, rolling_bars=rolling_bars)
        rows = calibration.rows
        for index, row in enumerate(rows):
            if row.level not in {"signal", "critical"}:
                continue
            forward_index = index + forward_bars
            if forward_index >= len(rows):
                continue
            future = rows[forward_index]
            forward_return = future.close - row.close
            forward_pct = ((future.close / row.close) - 1) * 100 if row.close else 0.0
            events.append(
                {
                    "symbol": symbol,
                    "open_time": row.open_time,
                    "level": row.level,
                    "direction": row.direction,
                    "score": row.score,
                    "entry_close": row.close,
                    "forward_pct": forward_pct,
                    "forward_return": forward_return,
                    "aligned": (forward_pct >= 0 and row.direction == "up")
                    or (forward_pct <= 0 and row.direction == "down"),
                }
            )

    aligned = [item for item in events if item["aligned"]]
    return {
        "symbols": symbols,
        "interval": interval,
        "lookback_days": lookback_days,
        "forward_bars": forward_bars,
        "event_count": len(events),
        "aligned_count": len(aligned),
        "alignment_rate": round(len(aligned) / len(events), 3) if events else 0.0,
        "avg_forward_pct": round(sum(item["forward_pct"] for item in events) / len(events), 3) if events else 0.0,
        "events": events[-20:],
    }