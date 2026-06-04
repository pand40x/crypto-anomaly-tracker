from __future__ import annotations


def explain_move(direction: str, volume_ratio: float, range_ratio: float, breakout: bool) -> str:
    side = "alım" if direction == "up" else "satış"
    parts = [f"hacimli {side}"]
    if range_ratio >= 1.8:
        parts.append("geniş mum")
    if breakout:
        parts.append("bant kırılımı")
    if volume_ratio < 1.8 and range_ratio < 1.8 and not breakout:
        parts.append("normal dışı fiyat hareketi")
    return ", ".join(parts)
