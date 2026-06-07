from __future__ import annotations

from datetime import datetime, timezone

from anomaly_tracker.models import AssetCalibration, SignalCandidate


def format_usd(value: float) -> str:
    return f"${value:,.0f}" if value >= 1000 else f"${value:,.2f}"


def format_price(value: float) -> str:
    if value >= 1000:
        return f"${value:,.0f}"
    if value >= 1:
        return f"${value:,.3f}"
    if value >= 0.01:
        return f"${value:,.4f}"
    return f"${value:,.6f}"


def format_compact_usd(value: float) -> str:
    if value >= 1_000_000_000:
        return f"${value / 1_000_000_000:.1f}B"
    if value >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:,.0f}"


def format_time(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def display_symbol(symbol: str) -> str:
    return symbol[:-4] if symbol.endswith("USDT") else symbol


def _level_text(level: str) -> str:
    return {
        "critical": "Kritik",
        "signal": "Sinyal",
        "watch": "İzleme",
    }.get(level, level)


def _direction_text(direction: str) -> str:
    return {
        "up": "Alım",
        "down": "Satış",
    }.get(direction, direction)


def _direction_label(direction: str) -> str:
    return _direction_text(direction).lower()


def _reason_text(reason: str) -> str:
    replacements = {
        "alim": "alım",
        "satis": "satış",
        "genis": "geniş",
        "band kirilimi": "bant kırılımı",
        "normal disi": "normal dışı",
    }
    result = reason
    for source, target in replacements.items():
        result = result.replace(source, target)
    return result


def _sentence_text(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


def _signal_emoji(candidate: SignalCandidate) -> str:
    if candidate.lane == "fast":
        return "⚡"
    if candidate.level == "critical":
        return "🚨"
    return "📈"


def _signal_label(candidate: SignalCandidate) -> str:
    if candidate.lane == "fast":
        prefix = "Hızlı"
    elif candidate.level == "critical":
        prefix = "Kritik"
    else:
        prefix = "Aktif"
    return f"{prefix} {_direction_label(candidate.direction)} sinyali"


def _headline(candidate: SignalCandidate, interval_text: str) -> str:
    return f"{_signal_emoji(candidate)} {display_symbol(candidate.symbol)} {candidate.pct_change:+.2f}% ({interval_text})"


def candidate_to_message(candidate: SignalCandidate) -> str:
    interval_text = {"1h": "1s", "4h": "4s", "1d": "1g"}.get(candidate.source_interval, candidate.source_interval)
    price_line = f"Fiyat: {format_price(candidate.close)}"
    if candidate.quote_volume > 0:
        price_line = f"{price_line} · Hacim: {format_compact_usd(candidate.quote_volume)}"
    lines = [
        _headline(candidate, interval_text),
        _signal_label(candidate),
        price_line,
        f"Neden: {_sentence_text(_reason_text(candidate.reason))}",
        f"Öncelik: #{candidate.global_rank} · Skor: {candidate.score:.2f}",
    ]
    return "\n".join(lines)


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
            "quote_volume": item.quote_volume,
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
        message = candidate_to_message(item).replace("\n", " / ")
        lines.append(
            f"| {item.global_rank} | {item.symbol} | {item.level} | {direction} | "
            f"{format_usd(item.close)} | {item.pct_change:+.2f}% | {item.score:.2f} | "
            f"{message} |"
        )

    lines.extend(["", "## Asset Esikleri", "", "| Asset | Watch | Signal | Critical | Son Skor |", "|---|---:|---:|---:|---:|"])
    for calibration in sorted(calibrations, key=lambda item: item.symbol):
        latest = calibration.rows[-1].score if calibration.rows else 0.0
        lines.append(
            f"| {calibration.symbol} | {calibration.thresholds.watch:.2f} | "
            f"{calibration.thresholds.signal:.2f} | {calibration.thresholds.critical:.2f} | {latest:.2f} |"
        )
    return "\n".join(lines) + "\n"
