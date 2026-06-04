from __future__ import annotations

from anomaly_tracker.models import AssetCalibration, MarketContext


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


def combined_market_context(
    calibrations: list[AssetCalibration],
    reference_symbols: list[str],
    risk_off_pct_change: float,
    risk_on_pct_change: float,
) -> MarketContext | None:
    contexts = [
        market_context_from_calibrations(
            calibrations,
            symbol,
            risk_off_pct_change,
            risk_on_pct_change,
        )
        for symbol in reference_symbols
    ]
    available = [item for item in contexts if item.reason != "reference_missing"]
    if not available:
        return MarketContext(
            reference_symbol=",".join(reference_symbols),
            pct_change=0.0,
            direction="flat",
            mode="neutral",
            reason="references_missing",
        )

    modes = [item.mode for item in available]
    if any(mode == "risk_off" for mode in modes):
        mode = "risk_off"
    elif all(mode == "risk_on" for mode in modes):
        mode = "risk_on"
    else:
        mode = "neutral"

    primary = available[0]
    reason = " | ".join(item.reason for item in available)
    return MarketContext(
        reference_symbol=",".join(item.reference_symbol for item in available),
        pct_change=primary.pct_change,
        direction=primary.direction,
        mode=mode,
        reason=reason,
    )