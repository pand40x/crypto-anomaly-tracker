from __future__ import annotations

from anomaly_tracker.models import AssetCalibration, SignalCandidate


def cooldown_key(candidate: SignalCandidate) -> str:
    return f"{candidate.symbol}|{candidate.lane}"


def dedupe_candidates_by_symbol(candidates: list[SignalCandidate]) -> list[SignalCandidate]:
    best: dict[str, SignalCandidate] = {}
    for candidate in sorted(candidates, key=lambda item: item.score, reverse=True):
        existing = best.get(candidate.symbol)
        if existing is None or candidate.score > existing.score:
            best[candidate.symbol] = candidate
    ranked = sorted(best.values(), key=lambda item: item.score, reverse=True)
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


def apply_confirmation_bonus(
    candidates: list[SignalCandidate],
    calibrations_by_interval: dict[str, list[AssetCalibration]],
    bonus: float,
    min_volume_ratio: float = 1.5,
) -> list[SignalCandidate]:
    if bonus <= 0:
        return candidates
    boosted: list[SignalCandidate] = []
    for candidate in candidates:
        other_interval = "1h" if candidate.source_interval == "4h" else "4h"
        calibration = next(
            (item for item in calibrations_by_interval.get(other_interval, []) if item.symbol == candidate.symbol),
            None,
        )
        extra_score = 0.0
        extra_reason = ""
        if calibration and calibration.rows:
            latest = calibration.rows[-1]
            if (
                latest.level in {"signal", "critical"}
                and latest.direction == candidate.direction
                and latest.volume_ratio >= min_volume_ratio
            ):
                extra_score = bonus
                extra_reason = f" +{other_interval} onay"
        boosted.append(
            SignalCandidate(
                symbol=candidate.symbol,
                open_time=candidate.open_time,
                close=candidate.close,
                pct_change=candidate.pct_change,
                score=candidate.score + extra_score,
                level=candidate.level,
                direction=candidate.direction,
                global_rank=candidate.global_rank,
                reason=candidate.reason + extra_reason if extra_reason else candidate.reason,
                source_interval=candidate.source_interval,
                lane=candidate.lane,
                quote_volume=candidate.quote_volume,
            )
        )
    return sorted(boosted, key=lambda item: item.score, reverse=True)