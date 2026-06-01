from __future__ import annotations


def explain_move(direction: str, volume_ratio: float, range_ratio: float, breakout: bool) -> str:
    side = "alim" if direction == "up" else "satis"
    parts = [f"hacimli {side}"]
    if range_ratio >= 1.8:
        parts.append("genis mum")
    if breakout:
        parts.append("band kirilimi")
    if volume_ratio < 1.8 and range_ratio < 1.8 and not breakout:
        parts.append("normal disi fiyat hareketi")
    return ", ".join(parts)
