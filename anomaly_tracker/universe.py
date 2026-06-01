from __future__ import annotations


STABLE_BASES = {
    "USDC",
    "FDUSD",
    "TUSD",
    "USDP",
    "DAI",
    "USD1",
    "RLUSD",
    "XUSD",
    "EUR",
    "EURI",
    "AEUR",
    "TRY",
    "BRL",
    "BIDR",
}
NON_CRYPTO_BASES = {"PAXG", "XAUT", "WBETH"}
LEVERAGED_SUFFIXES = ("UP", "DOWN", "BULL", "BEAR")


def _base_asset(symbol: str) -> str:
    return symbol[:-4] if symbol.endswith("USDT") else symbol


def _is_allowed_symbol(info: dict) -> bool:
    symbol = str(info.get("symbol", ""))
    base = str(info.get("baseAsset") or _base_asset(symbol))
    if info.get("status") != "TRADING":
        return False
    if not info.get("isSpotTradingAllowed", False):
        return False
    if info.get("quoteAsset") != "USDT":
        return False
    if not symbol.endswith("USDT"):
        return False
    if not base.isascii() or not base.isalnum():
        return False
    if base in STABLE_BASES:
        return False
    if base in NON_CRYPTO_BASES:
        return False
    return not any(base.endswith(suffix) for suffix in LEVERAGED_SUFFIXES)


def select_top_usdt_symbols(exchange_info: dict, tickers: list[dict], limit: int = 150) -> list[str]:
    allowed = {
        item["symbol"]
        for item in exchange_info.get("symbols", [])
        if _is_allowed_symbol(item)
    }
    volumes: list[tuple[str, float]] = []
    for ticker in tickers:
        symbol = str(ticker.get("symbol", ""))
        if symbol not in allowed:
            continue
        try:
            quote_volume = float(ticker.get("quoteVolume", 0))
        except (TypeError, ValueError):
            quote_volume = 0.0
        volumes.append((symbol, quote_volume))
    volumes.sort(key=lambda item: item[1], reverse=True)
    return [symbol for symbol, _ in volumes[:limit]]
