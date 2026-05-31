from __future__ import annotations

import json
from pathlib import Path

from anomaly_tracker.binance import BinanceClient
from anomaly_tracker.models import AssetCalibration, SignalCandidate
from anomaly_tracker.outputs import candidate_to_message, candidates_to_jsonable, markdown_report
from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.scoring import calibrate_asset, select_signal_candidates
from anomaly_tracker.state import CooldownState
from anomaly_tracker.telegram import send_message
from anomaly_tracker.universe import select_top_usdt_symbols


def persist_scan_result(
    output_dir: Path,
    calibrations: list[AssetCalibration],
    candidates: list[SignalCandidate],
    sendable: list[SignalCandidate],
    symbols_scanned: list[str],
    interval: str,
    lookback_days: int,
) -> dict:
    output_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "interval": interval,
        "lookback_days": lookback_days,
        "symbols_scanned": symbols_scanned,
        "candidate_count": len(candidates),
        "sendable_count": len(sendable),
        "candidates": candidates_to_jsonable(candidates),
        "sendable": candidates_to_jsonable(sendable),
    }
    (output_dir / "latest_crypto_signals.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
    (output_dir / "latest_crypto_scan.md").write_text(markdown_report(calibrations, candidates), encoding="utf-8")
    return payload


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
    for symbol in selected_symbols:
        candles = client.klines(symbol, config.interval, start_ms, end_ms)
        if len(candles) < max(config.rolling_bars + 10, 60):
            continue
        calibrations.append(calibrate_asset(symbol, candles, rolling_bars=config.rolling_bars))

    candidates = select_signal_candidates(
        calibrations,
        global_limit=config.global_limit,
        min_abs_pct_change=config.min_abs_pct_change,
        min_volume_ratio=config.min_volume_ratio,
    )
    cooldown = CooldownState(config.state_path, cooldown_seconds=config.cooldown_seconds)
    sendable = [candidate for candidate in candidates if cooldown.should_send(candidate)]

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
        [item.symbol for item in calibrations],
        config.interval,
        config.lookback_days,
    )
    payload["sent_symbols"] = sent_symbols
    return payload
