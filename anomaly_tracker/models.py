from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    symbol: str
    open_time: int
    close_time: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    quote_volume: float


@dataclass(frozen=True)
class Thresholds:
    watch: float
    signal: float
    critical: float


@dataclass(frozen=True)
class ScoredRow:
    symbol: str
    open_time: int
    close: float
    pct_change: float
    score: float
    level: str
    direction: str
    return_z: float
    volume_ratio: float
    range_ratio: float
    breakout: bool
    reason: str


@dataclass(frozen=True)
class AssetCalibration:
    symbol: str
    thresholds: Thresholds
    rows: list[ScoredRow]


@dataclass(frozen=True)
class SignalCandidate:
    symbol: str
    open_time: int
    close: float
    pct_change: float
    score: float
    level: str
    direction: str
    global_rank: int
    reason: str
    source_interval: str = "4h"
    lane: str = "main"
