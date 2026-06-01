from __future__ import annotations

from datetime import datetime, timezone

from anomaly_tracker.models import AssetCalibration, SignalCandidate


def format_usd(value: float) -> str:
    return f"${value:,.0f}" if value >= 1000 else f"${value:,.2f}"


def format_time(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def display_symbol(symbol: str) -> str:
    return symbol[:-4] if symbol.endswith("USDT") else symbol


def candidate_to_message(candidate: SignalCandidate) -> str:
    direction = "yukselis" if candidate.direction == "up" else "dusus"
    interval_text = {"1h": "1 saatte", "4h": "4 saatte", "1d": "1 gunde"}.get(candidate.source_interval, candidate.source_interval)
    lane_text = " fast-lane" if candidate.lane == "fast" else ""
    return (
        f"{display_symbol(candidate.symbol)} icin olagandisi{lane_text} {direction}: "
        f"fiyat son {interval_text} {candidate.pct_change:+.2f}% hareketle "
        f"{format_usd(candidate.close)} seviyesine geldi. {candidate.reason} "
        f"Bu bir haber iddiasi degil; piyasanin normal ritminin disina ciktigini soyleyen erken uyari."
    )


def candidates_to_jsonable(candidates: list[SignalCandidate]) -> list[dict]:
    return [
        {
            "symbol": item.symbol,
            "time": format_time(item.open_time),
            "open_time": item.open_time,
            "close": item.close,
            "pct_change": item.pct_change,
            "score": item.score,
            "level": item.level,
            "direction": item.direction,
            "global_rank": item.global_rank,
            "reason": item.reason,
            "source_interval": item.source_interval,
            "lane": item.lane,
            "message": candidate_to_message(item),
        }
        for item in candidates
    ]


def markdown_report(calibrations: list[AssetCalibration], candidates: list[SignalCandidate]) -> str:
    lines = [
        "# Crypto Anomaly Scan",
        "",
        "## Telegram Adaylari",
        "",
        "| Rank | Asset | Seviye | Yon | Fiyat | 4s | Skor | Mesaj |",
        "|---:|---|---|---|---:|---:|---:|---|",
    ]
    if not candidates:
        lines.append("| - | - | - | - | - | - | - | Sinyal yok |")
    for item in candidates:
        direction = "yukari" if item.direction == "up" else "asagi"
        lines.append(
            f"| {item.global_rank} | {item.symbol} | {item.level} | {direction} | "
            f"{format_usd(item.close)} | {item.pct_change:+.2f}% | {item.score:.2f} | "
            f"{candidate_to_message(item)} |"
        )

    lines.extend(["", "## Asset Esikleri", "", "| Asset | Watch | Signal | Critical | Son Skor |", "|---|---:|---:|---:|---:|"])
    for calibration in sorted(calibrations, key=lambda item: item.symbol):
        latest = calibration.rows[-1].score if calibration.rows else 0.0
        lines.append(
            f"| {calibration.symbol} | {calibration.thresholds.watch:.2f} | "
            f"{calibration.thresholds.signal:.2f} | {calibration.thresholds.critical:.2f} | {latest:.2f} |"
        )
    return "\n".join(lines) + "\n"
