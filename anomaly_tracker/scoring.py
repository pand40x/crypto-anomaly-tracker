from __future__ import annotations

import math
import statistics

from anomaly_tracker.humanize import explain_move
from anomaly_tracker.models import AssetCalibration, Candle, MarketContext, ScoredRow, SignalCandidate, Thresholds


def _median(values: list[float]) -> float:
    return statistics.median(values) if values else 0.0


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[int(rank)]
    return ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower)


def _robust_z(value: float, history: list[float]) -> float:
    med = _median(history)
    mad = _median([abs(item - med) for item in history])
    if mad > 1e-12:
        return (value - med) / (1.4826 * mad)
    stdev = statistics.pstdev(history) if len(history) > 1 else 0.0
    return 0.0 if stdev <= 1e-12 else (value - med) / stdev


def _level(score: float, thresholds: Thresholds) -> str:
    if score >= thresholds.critical:
        return "critical"
    if score >= thresholds.signal:
        return "signal"
    if score >= thresholds.watch:
        return "watch"
    return "normal"


def _score_components(
    return_z: float,
    volume_ratio: float,
    range_ratio: float,
    breakout: bool,
    market_divergence: float = 0.0,
) -> float:
    price_component = min(abs(return_z), 10.0)
    volume_component = min(max(math.log(max(volume_ratio, 1e-9), 2), 0.0) * 2.0, 6.0)
    range_component = min(max(math.log(max(range_ratio, 1e-9), 2), 0.0) * 2.0, 5.0)
    breakout_component = 1.0 if breakout else 0.0
    divergence_component = min(abs(market_divergence), 5.0)
    return (
        0.40 * price_component
        + 0.25 * volume_component
        + 0.15 * range_component
        + 0.10 * breakout_component
        + 0.10 * divergence_component
    )


def calibrate_asset(
    symbol: str,
    candles: list[Candle],
    rolling_bars: int = 42,
    watch_pct: float = 0.95,
    signal_pct: float = 0.985,
    critical_pct: float = 0.995,
) -> AssetCalibration:
    returns: list[float] = []
    quote_volumes: list[float] = []
    ranges: list[float] = []
    provisional: list[dict] = []

    for i, candle in enumerate(candles):
        if i == 0:
            returns.append(0.0)
            quote_volumes.append(candle.quote_volume)
            ranges.append(0.0)
            continue

        previous = candles[i - 1]
        pct_change = ((candle.close / previous.close) - 1) * 100
        log_return = math.log(candle.close / previous.close) * 100
        candle_range = ((candle.high - candle.low) / candle.open) * 100 if candle.open else 0.0
        start = max(0, i - rolling_bars)
        ret_hist = returns[start:i]
        vol_hist = quote_volumes[start:i]
        range_hist = ranges[start:i]
        close_hist = [item.close for item in candles[start:i]]

        if len(ret_hist) >= rolling_bars:
            return_z = _robust_z(log_return, ret_hist)
            volume_base = _median(vol_hist)
            range_base = _median(range_hist)
            volume_ratio = candle.quote_volume / volume_base if volume_base > 0 else 1.0
            range_ratio = candle_range / range_base if range_base > 0 else 1.0
            direction = "up" if pct_change >= 0 else "down"
            breakout = candle.close > max(close_hist) if direction == "up" else candle.close < min(close_hist)
            score = _score_components(return_z, volume_ratio, range_ratio, breakout)
            provisional.append(
                {
                    "symbol": symbol,
                    "open_time": candle.open_time,
                    "close": candle.close,
                    "pct_change": pct_change,
                    "score": score,
                    "direction": direction,
                    "return_z": return_z,
                    "volume_ratio": volume_ratio,
                    "range_ratio": range_ratio,
                    "breakout": breakout,
                    "quote_volume": candle.quote_volume,
                }
            )

        returns.append(log_return)
        quote_volumes.append(candle.quote_volume)
        ranges.append(candle_range)

    scores = [row["score"] for row in provisional]
    thresholds = Thresholds(
        watch=_percentile(scores, watch_pct),
        signal=_percentile(scores, signal_pct),
        critical=_percentile(scores, critical_pct),
    )
    rows = [
        ScoredRow(
            symbol=row["symbol"],
            open_time=row["open_time"],
            close=row["close"],
            pct_change=row["pct_change"],
            score=row["score"],
            level=_level(row["score"], thresholds),
            direction=row["direction"],
            return_z=row["return_z"],
            volume_ratio=row["volume_ratio"],
            range_ratio=row["range_ratio"],
            breakout=row["breakout"],
            reason=explain_move(row["direction"], row["volume_ratio"], row["range_ratio"], row["breakout"]),
            quote_volume=row["quote_volume"],
        )
        for row in provisional
    ]
    return AssetCalibration(symbol=symbol, thresholds=thresholds, rows=rows)


def select_signal_candidates(
    calibrations: list[AssetCalibration],
    global_limit: int = 10,
    min_abs_pct_change: float = 1.0,
    min_volume_ratio: float = 1.5,
) -> list[SignalCandidate]:
    latest_signal_rows: list[ScoredRow] = []
    for calibration in calibrations:
        if not calibration.rows:
            continue
        row = calibration.rows[-1]
        if row.level in {"signal", "critical"} and (
            abs(row.pct_change) >= min_abs_pct_change or row.volume_ratio >= min_volume_ratio
        ):
            latest_signal_rows.append(row)

    ranked = sorted(latest_signal_rows, key=lambda row: row.score, reverse=True)[:global_limit]
    return [
        SignalCandidate(
            symbol=row.symbol,
            open_time=row.open_time,
            close=row.close,
            pct_change=row.pct_change,
            score=row.score,
            level=row.level,
            direction=row.direction,
            global_rank=index,
            reason=row.reason,
            quote_volume=row.quote_volume,
        )
        for index, row in enumerate(ranked, start=1)
    ]


def market_filter_decision(candidate: SignalCandidate, context: MarketContext) -> dict:
    if context.mode == "risk_off" and candidate.direction == "up":
        if candidate.level == "critical":
            return {"keep": True, "reason": "critical_override", "market_mode": context.mode}
        return {"keep": False, "reason": "risk_off_weak_bullish", "market_mode": context.mode}
    if context.mode == "risk_on" and candidate.direction == "down":
        if candidate.level == "critical":
            return {"keep": True, "reason": "critical_override", "market_mode": context.mode}
        return {"keep": False, "reason": "risk_on_weak_bearish", "market_mode": context.mode}
    return {"keep": True, "reason": "market_aligned_or_neutral", "market_mode": context.mode}
