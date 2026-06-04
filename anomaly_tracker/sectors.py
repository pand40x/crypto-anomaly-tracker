from __future__ import annotations

from dataclasses import dataclass

from anomaly_tracker.models import SignalCandidate


SECTOR_LABELS = {
    "ai": "Yapay Zeka",
    "meme": "Meme",
    "l2": "L2 / Ölçekleme",
    "defi": "DeFi",
    "gaming": "Oyun / Metaverse",
    "infra": "Altyapı",
    "exchange": "Borsa Token",
}


SECTOR_SYMBOLS: dict[str, set[str]] = {
    "ai": {
        "FETUSDT", "RENDERUSDT", "TAOUSDT", "NEARUSDT", "ARKMUSDT", "WLDUSDT", "IOUSDT", "AIUSDT",
    },
    "meme": {
        "DOGEUSDT", "SHIBUSDT", "PEPEUSDT", "FLOKIUSDT", "BONKUSDT", "WIFUSDT", "NEIROUSDT", "BOMEUSDT",
    },
    "l2": {
        "ARBUSDT", "OPUSDT", "MATICUSDT", "POLUSDT", "STRKUSDT", "ZKUSDT", "MANTAUSDT", "IMXUSDT",
    },
    "defi": {
        "UNIUSDT", "AAVEUSDT", "MKRUSDT", "CRVUSDT", "LDOUSDT", "PENDLEUSDT", "ENAUSDT", "RUNEUSDT",
    },
    "gaming": {
        "AXSUSDT", "SANDUSDT", "GALAUSDT", "PIXELUSDT", "PORTALUSDT", "BEAMXUSDT", "RONINUSDT",
    },
    "infra": {
        "LINKUSDT", "DOTUSDT", "ATOMUSDT", "FILUSDT", "ICPUSDT", "TIAUSDT", "SEIUSDT", "SUIUSDT",
    },
    "exchange": {
        "BNBUSDT", "OKBUSDT", "CROUSDT", "GTUSDT",
    },
}


SYMBOL_TO_SECTOR: dict[str, str] = {}
for sector_id, symbols in SECTOR_SYMBOLS.items():
    for symbol in symbols:
        SYMBOL_TO_SECTOR[symbol] = sector_id


@dataclass(frozen=True)
class SectorHeat:
    sector_id: str
    label: str
    direction: str
    count: int
    symbols: tuple[str, ...]
    avg_score: float


def sector_for_symbol(symbol: str) -> str | None:
    return SYMBOL_TO_SECTOR.get(symbol)


def detect_sector_heat(
    candidates: list[SignalCandidate],
    min_count: int = 3,
    min_avg_score: float = 0.0,
) -> list[SectorHeat]:
    buckets: dict[tuple[str, str], list[SignalCandidate]] = {}
    for candidate in candidates:
        sector_id = sector_for_symbol(candidate.symbol)
        if sector_id is None:
            continue
        key = (sector_id, candidate.direction)
        buckets.setdefault(key, []).append(candidate)

    heats: list[SectorHeat] = []
    for (sector_id, direction), group in buckets.items():
        if len(group) < min_count:
            continue
        avg_score = sum(item.score for item in group) / len(group)
        if avg_score < min_avg_score:
            continue
        heats.append(
            SectorHeat(
                sector_id=sector_id,
                label=SECTOR_LABELS.get(sector_id, sector_id),
                direction=direction,
                count=len(group),
                symbols=tuple(sorted({item.symbol for item in group})),
                avg_score=round(avg_score, 3),
            )
        )
    return sorted(heats, key=lambda item: (item.count, item.avg_score), reverse=True)


def sector_heat_to_jsonable(heats: list[SectorHeat]) -> list[dict]:
    return [
        {
            "sector_id": item.sector_id,
            "label": item.label,
            "direction": item.direction,
            "count": item.count,
            "symbols": list(item.symbols),
            "avg_score": item.avg_score,
        }
        for item in heats
    ]