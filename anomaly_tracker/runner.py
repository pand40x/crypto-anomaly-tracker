from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from anomaly_tracker.binance import BinanceClient
from anomaly_tracker.candidates import apply_confirmation_bonus, dedupe_candidates_by_symbol
from anomaly_tracker.market import combined_market_context, market_context_from_calibrations
from anomaly_tracker.models import AssetCalibration, MarketContext, SignalCandidate
from anomaly_tracker.outputs import candidate_to_message, candidates_to_jsonable, markdown_report
from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.scoring import calibrate_asset, market_filter_decision, select_signal_candidates
from anomaly_tracker.sectors import detect_sector_heat, sector_heat_to_jsonable
from anomaly_tracker.state import CooldownState
from anomaly_tracker.telegram import send_message
from anomaly_tracker.universe import select_top_usdt_symbols
from anomaly_tracker.watchlist import WatchlistStore, watchlist_send_override


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
    sector_heat: list[dict] | None = None,
    watchlist_symbols: list[str] | None = None,
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
        "sector_heat": sector_heat or [],
        "watchlist_symbols": watchlist_symbols or [],
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


def _calibrate_symbol(
    symbol: str,
    config: AppConfig,
    start_ms: int,
    end_ms: int,
    client: BinanceClient,
) -> AssetCalibration | None:
    candles = client.klines(symbol, config.interval, start_ms, end_ms)
    candles_per_day = 6 if config.interval == "4h" else 24 if config.interval == "1h" else 1
    min_candles = max(config.rolling_bars + 10, config.min_history_days * candles_per_day)
    if len(candles) < min_candles:
        return None
    return calibrate_asset(
        symbol,
        candles,
        rolling_bars=config.rolling_bars,
        watch_pct=config.watch_pct,
        signal_pct=config.signal_pct,
        critical_pct=config.critical_pct,
    )


def _calibrate_symbol_with_params(
    symbol: str,
    interval: str,
    rolling_bars: int,
    min_history_days: int,
    start_ms: int,
    end_ms: int,
    client: BinanceClient,
    watch_pct: float,
    signal_pct: float,
    critical_pct: float,
) -> AssetCalibration | None:
    candles = client.klines(symbol, interval, start_ms, end_ms)
    candles_per_day = 6 if interval == "4h" else 24 if interval == "1h" else 1
    min_candles = max(rolling_bars + 10, min_history_days * candles_per_day)
    if len(candles) < min_candles:
        return None
    return calibrate_asset(
        symbol,
        candles,
        rolling_bars=rolling_bars,
        watch_pct=watch_pct,
        signal_pct=signal_pct,
        critical_pct=critical_pct,
    )


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
    watchlist = WatchlistStore(config.watchlist_path)
    end_ms = client.server_time_ms()
    start_ms = end_ms - config.lookback_days * 24 * 60 * 60 * 1000
    if symbols:
        selected_symbols = symbols
    else:
        top_symbols = select_top_usdt_symbols(
            client.exchange_info(),
            client.ticker_24hr(),
            limit=config.symbol_limit,
        )
        selected_symbols = list(dict.fromkeys(top_symbols + watchlist.symbols()))

    calibrations: list[AssetCalibration] = []
    fast_calibrations: list[AssetCalibration] = []
    with ThreadPoolExecutor(max_workers=max(1, config.scan_workers)) as executor:
        futures = {
            executor.submit(_calibrate_symbol, symbol, config, start_ms, end_ms, client): symbol
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
    watchlist_symbols = set(watchlist.symbols())
    if watchlist_symbols:
        relaxed = select_signal_candidates(
            calibrations,
            global_limit=raw_limit,
            min_abs_pct_change=config.min_abs_pct_change * config.watchlist_min_pct_factor,
            min_volume_ratio=config.min_volume_ratio,
        )
        seen = {item.symbol for item in candidates}
        for item in relaxed:
            if item.symbol in watchlist_symbols and item.symbol not in seen:
                candidates.append(item)
                seen.add(item.symbol)
    if config.fast_lane_enabled:
        fast_start_ms = end_ms - config.fast_lookback_days * 24 * 60 * 60 * 1000
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
                    client,
                    config.watch_pct,
                    config.signal_pct,
                    config.critical_pct,
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
    candidates = dedupe_candidates_by_symbol(candidates)
    candidates = apply_confirmation_bonus(
        candidates,
        {
            config.interval: calibrations,
            config.fast_interval: fast_calibrations,
        },
        bonus=config.confirmation_bonus,
        min_volume_ratio=config.min_volume_ratio,
    )
    candidates = _rerank_candidates(candidates, raw_limit)
    market_context = None
    if config.market_filter_enabled:
        references = list(dict.fromkeys(config.market_reference_symbols))
        market_context = (
            combined_market_context(
                calibrations,
                references,
                config.market_risk_off_pct_change,
                config.market_risk_on_pct_change,
            )
            if len(references) > 1
            else market_context_from_calibrations(
                calibrations,
                references[0],
                config.market_risk_off_pct_change,
                config.market_risk_on_pct_change,
            )
        )
    sector_heat = sector_heat_to_jsonable(
        detect_sector_heat(
            candidates,
            min_count=config.sector_min_count,
            min_avg_score=config.sector_min_avg_score,
        )
    )
    candidates, filtered, market_filter_decisions = apply_market_filter(
        candidates,
        market_context,
        config.global_limit,
    )
    cooldown = CooldownState(config.state_path, cooldown_seconds=config.cooldown_seconds)
    send_decisions = {}
    for candidate in candidates:
        base = cooldown.send_decision(candidate)
        override = watchlist_send_override(
            watchlist.get(candidate.symbol),
            candidate.level,
            base["send"],
            base["reason"],
        )
        send_decisions[candidate_decision_key(candidate)] = override
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
        for heat in sector_heat:
            if heat["count"] >= config.sector_alert_min_count:
                direction = "yükseliş" if heat["direction"] == "up" else "düşüş"
                symbols_text = ", ".join(heat["symbols"][:6])
                send_message(
                    config.telegram_bot_token,
                    config.telegram_chat_id,
                    "\n".join(
                        [
                            f"🧺 SEKTÖR ISINMASI | {heat['label']}",
                            f"{heat['count']} coin aynı yönde ({direction})",
                            f"Ort. skor: {heat['avg_score']}",
                            f"Semboller: {symbols_text}",
                        ]
                    ),
                )

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
        sector_heat=sector_heat,
        watchlist_symbols=watchlist.symbols(),
    )
    payload["sent_symbols"] = sent_symbols
    payload["sector_heat"] = sector_heat
    return payload
