from __future__ import annotations


def explain_move(direction: str, volume_ratio: float, range_ratio: float, breakout: bool) -> str:
    move_word = "yukseldi" if direction == "up" else "dustu"
    parts = [f"Fiyat kendi normaline gore belirgin sekilde {move_word}."]
    if volume_ratio >= 1.8:
        parts.append(f"Hacim normale gore {volume_ratio:.1f}x canlandi.")
    elif volume_ratio >= 1.25:
        parts.append("Hacim normalin uzerinde.")
    if range_ratio >= 1.8:
        parts.append("Mum araligi genisledi; piyasa hizli karar degistiriyor.")
    if breakout:
        parts.append("Fiyat son haftalik bandin disina tasti.")
    return " ".join(parts)
