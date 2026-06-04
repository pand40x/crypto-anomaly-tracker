from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from anomaly_tracker.binance import BinanceClient
from anomaly_tracker.models import AssetCalibration, MarketContext, SignalCandidate
from anomaly_tracker.outputs import candidate_to_message, candidates_to_jsonable, markdown_report
from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.scoring import calibrate_asset, market_filter_decision, select_signal_candidates
from anomaly_tracker.state import CooldownState
from anomaly_tracker.telegram import send_message
from anomaly_tracker.universe import select_top_usdt_symbols


def persist_scan_result(
    output_dir: Path,
    calibrations: list[AssetCalibration],
    candidates: list[SignalCandidate],
    sendable: list[SignalCandidate],
    suppressed: list[SignalCandidate],
    send_decisions: dict[str, dict],
    filtered: list[SignalCandidate],
    market_filter_decisions: dict[str, dict],
    market_context: MarketContext | None,
    symbols_scanned: list[str],
    interval: str,
    lookback_days: int,
    raw_candidate_count: int | None = None,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "interval": interval,
        "lookback_days": lookback_days,
        "symbols_scanned": symbols_scanned,
        "raw_candidate_count": len(candidates) if raw_candidate_count is None else raw_candidate_count,
        "candidate_count": len(candidates),
        "sendable_count": len(sendable),
        "suppressed_count": len(suppressed),
        "filtered_count": len(filtered),
        "market_context": _market_context_to_jsonable(market_context),
        "market_filter_decisions": market_filter_decisions,
        "send_decisions": send_decisions,
        "candidates": _candidates_to_jsonable_with_decisions(candidates, send_decisions, market_filter_decisions),
        "sendable": _candidates_to_jsonable_with_decisions(sendable, send_decisions, market_filter_decisions),
        "suppressed": _candidates_to_jsonable_with_decisions(suppressed, send_decisions, market_filter_decisions),
        "filtered": _candidates_to_jsonable_with_decisions(filtered, send_decisions, market_filter_decisions),
    }
    (output_dir / "latest_crypto_signals.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output_dir / "latest_crypto_scan.md").write_text(markdown_report(calibrations, candidates), encoding="utf-8")
    return payload


def candidate_decision_key(candidate: SignalCandidate) -> str:
    return f"{candidate.symbol}|{candidate.source_interval}|{candidate.lane}|{candidate.open_time}"


def _market_context_to_jsonable(context: MarketContext | None) -> dict | None:
    if context is None:
        return None
    return {
        "reference_symbol": context.reference_symbol,
        "pct_change": context.pct_change,
        "direction": context.direction,
        "mode": context.mode,
        "reason": context.reason,
    }


def _candidates_to_jsonable_with_decisions(
    candidates: list[SignalCandidate],
    send_decisions: dict[str, dict],
    market_filter_decisions: dict[str, dict] | None = None,
) -> list[dict]:
    payload = candidates_to_jsonable(candidates)
    for item, candidate in zip(payload, candidates):
        key = candidate_decision_key(candidate)
        item["send_decision"] = send_decisions.get(key, {"send": False, "reason": "unknown"})
        if market_filter_decisions is not None:
            item["market_filter_decision"] = market_filter_decisions.get(key, {"keep": True, "reason": "not_evaluated"})
    return payload


def market_context_from_calibrations(
    calibrations: list[AssetCalibration],
    reference_symbol: str,
    risk_off_pct_change: float,
    risk_on_pct_change: float,
) -> MarketContext:
    calibration = next((item for item in calibrations if item.symbol == reference_symbol and item.rows), None)
    if calibration is None:
        return MarketContext(reference_symbol, 0.0, "flat", "neutral", "reference_missing")
    latest = calibration.rows[-1]
    if latest.pct_change <= risk_off_pct_change:
        mode = "risk_off"
    elif latest.pct_change >= risk_on_pct_change:
        mode = "risk_on"
    else:
        mode = "neutral"
    return MarketContext(
        reference_symbol=reference_symbol,
        pct_change=latest.pct_change,
        direction=latest.direction,
        mode=mode,
        reason=f"{reference_symbol} {latest.pct_change:+.2f}%",
    )


def _rerank_candidates(candidates: list[SignalCandidate], global_limit: int) -> list[SignalCandidate]:
    ranked = sorted(candidates, key=lambda item: item.score, reverse=True)[:global_limit]
    return [
        SignalCandidate(
            symbol=item.symbol,
            open_time=item.open_time,
            close=item.close,
            pct_change=item.pct_change,
            score=item.score,
            level=item.level,
            direction=item.direction,
            global_rank=index,
            reason=item.reason,
            source_interval=item.source_interval,
            lane=item.lane,
            quote_volume=item.quote_volume,
        )
        for index, item in enumerate(ranked, start=1)
    ]


def apply_market_filter(
    candidates: list[SignalCandidate],
    context: MarketContext | None,
    global_limit: int,
) -> tuple[list[SignalCandidate], list[SignalCandidate], dict[str, dict]]:
    if context is None or context.mode == "neutral":
        kept = _rerank_candidates(candidates, global_limit)
        return kept, [], {
            candidate_decision_key(candidate): {"keep": True, "reason": "market_filter_disabled_or_neutral"}
            for candidate in candidates
        }

    kept: list[SignalCandidate] = []
    filtered: list[SignalCandidate] = []
    decisions: dict[str, dict] = {}
    for candidate in candidates:
        decision = market_filter_decision(candidate, context)
        decisions[candidate_decision_key(candidate)] = decision
        if decision["keep"]:
            kept.append(candidate)
        else:
            filtered.append(candidate)
    return _rerank_candidates(kept, global_limit), filtered, decisions


def _calibrate_symbol(symbol: str, config: AppConfig, start_ms: int, end_ms: int) -> AssetCalibration | None:
    client = BinanceClient()
    candles = client.klines(symbol, config.interval, start_ms, end_ms)
    candles_per_day = 6 if config.interval == "4h" else 24 if config.interval == "1h" else 1
    min_candles = max(config.rolling_bars + 10, config.min_history_days * candles_per_day)
    if len(candles) < min_candles:
        return None
    return calibrate_asset(symbol, candles, rolling_bars=config.rolling_bars)


def _calibrate_symbol_with_params(
    symbol: str,
    interval: str,
    rolling_bars: int,
    min_history_days: int,
    start_ms: int,
    end_ms: int,
) -> AssetCalibration | None:
    client = BinanceClient()
    candles = client.klines(symbol, interval, start_ms, end_ms)
    candles_per_day = 6 if interval == "4h" else 24 if interval == "1h" else 1
    min_candles = max(rolling_bars + 10, min_history_days * candles_per_day)
    if len(candles) < min_candles:
        return None
    return calibrate_asset(symbol, candles, rolling_bars=rolling_bars)


def fast_lane_candidates(
    calibrations: list[AssetCalibration],
    global_limit: int = 10,
    min_abs_pct_change: float = 1.0,
    min_volume_ratio: float = 3.0,
) -> list[SignalCandidate]:
    candidates = select_signal_candidates(
        calibrations,
        global_limit=global_limit,
        min_abs_pct_change=min_abs_pct_change,
        min_volume_ratio=min_volume_ratio,
    )
    fast = [candidate for candidate in candidates if candidate.level == "critical"]
    return [
        SignalCandidate(
            symbol=candidate.symbol,
            open_time=candidate.open_time,
            close=candidate.close,
            pct_change=candidate.pct_change,
            score=candidate.score,
            level=candidate.level,
            direction=candidate.direction,
            global_rank=index,
            reason=candidate.reason,
            source_interval="1h",
            lane="fast",
            quote_volume=candidate.quote_volume,
        )
        for index, candidate in enumerate(fast[:global_limit], start=1)
    ]


def run_scan(config: AppConfig, send_telegram: bool = False, symbols: list[str] | None = None) -> dict:
    client = BinanceClient()
    end_ms = client.server_time_ms()
    start_ms = end_ms - config.lookback_days * 24 * 60 * 60 * 1000
    selected_symbols = symbols or select_top_usdt_symbols(
        client.exchange_info(),
        client.ticker_24hr(),
        limit=config.symbol_limit,
    )

    calibrations = []
    with ThreadPoolExecutor(max_workers=max(1, config.scan_workers)) as executor:
        futures = {
            executor.submit(_calibrate_symbol, symbol, config, start_ms, end_ms): symbol
            for symbol in selected_symbols
        }
        for future in as_completed(futures):
            symbol = futures[future]
            try:
                calibration = future.result()
                if calibration:
                    calibrations.append(calibration)
            except Exception as exc:
                print(f"scan warning: {symbol} skipped: {exc}", flush=True)

    raw_limit = max(config.global_limit, config.global_limit * 2)
    candidates = select_signal_candidates(
        calibrations,
        global_limit=raw_limit,
        min_abs_pct_change=config.min_abs_pct_change,
        min_volume_ratio=config.min_volume_ratio,
    )
    if config.fast_lane_enabled:
        fast_start_ms = end_ms - config.fast_lookback_days * 24 * 60 * 60 * 1000
        fast_calibrations = []
        with ThreadPoolExecutor(max_workers=max(1, config.scan_workers)) as executor:
            futures = {
                executor.submit(
                    _calibrate_symbol_with_params,
                    symbol,
                    config.fast_interval,
                    config.fast_rolling_bars,
                    config.min_history_days,
                    fast_start_ms,
                    end_ms,
                ): symbol
                for symbol in selected_symbols
            }
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    calibration = future.result()
                    if calibration:
                        fast_calibrations.append(calibration)
                except Exception as exc:
                    print(f"fast-lane warning: {symbol} skipped: {exc}", flush=True)
        candidates.extend(
            fast_lane_candidates(
                fast_calibrations,
                global_limit=raw_limit,
                min_abs_pct_change=config.fast_min_abs_pct_change,
                min_volume_ratio=config.fast_min_volume_ratio,
            )
        )
    raw_candidate_count = len(candidates)
    market_context = (
        market_context_from_calibrations(
            calibrations,
            config.market_reference_symbol,
            config.market_risk_off_pct_change,
            config.market_risk_on_pct_change,
        )
        if config.market_filter_enabled
        else None
    )
    candidates, filtered, market_filter_decisions = apply_market_filter(
        candidates,
        market_context,
        config.global_limit,
    )
    cooldown = CooldownState(config.state_path, cooldown_seconds=config.cooldown_seconds)
    send_decisions = {
        candidate_decision_key(candidate): cooldown.send_decision(candidate)
        for candidate in candidates
    }
    sendable = [
        candidate
        for candidate in candidates
        if send_decisions[candidate_decision_key(candidate)]["send"]
    ]
    suppressed = [
        candidate
        for candidate in candidates
        if not send_decisions[candidate_decision_key(candidate)]["send"]
    ]

    sent_symbols: list[str] = []
    if send_telegram and config.telegram_bot_token and config.telegram_chat_id:
        for candidate in sendable:
            send_message(config.telegram_bot_token, config.telegram_chat_id, candidate_to_message(candidate))
            cooldown.record_sent(candidate)
            sent_symbols.append(candidate.symbol)

    payload = persist_scan_result(
        config.output_dir,
        calibrations,
        candidates,
        sendable,
        suppressed,
        send_decisions,
        filtered,
        market_filter_decisions,
        market_context,
        [item.symbol for item in calibrations],
        config.interval,
        config.lookback_days,
        raw_candidate_count=raw_candidate_count,
    )
    payload["sent_symbols"] = sent_symbols
    return payload
