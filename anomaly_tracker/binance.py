from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request

from anomaly_tracker.models import Candle


class BinanceClient:
    def __init__(self, base_url: str = "https://api.binance.com", pause_seconds: float = 0.08):
        self.base_url = base_url.rstrip("/")
        self.pause_seconds = pause_seconds

    def _get_json(self, path: str, params: dict[str, int | str] | None = None):
        query = "?" + urllib.parse.urlencode(params) if params else ""
        request = urllib.request.Request(
            self.base_url + path + query,
            headers={"User-Agent": "codex-anomaly-tracker/0.1"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))

    def server_time_ms(self) -> int:
        return int(self._get_json("/api/v3/time")["serverTime"])

    def exchange_info(self) -> dict:
        return self._get_json("/api/v3/exchangeInfo")

    def ticker_24hr(self) -> list[dict]:
        return self._get_json("/api/v3/ticker/24hr")

    def klines(self, symbol: str, interval: str, start_ms: int, end_ms: int) -> list[Candle]:
        candles: list[Candle] = []
        cursor = start_ms
        while cursor < end_ms:
            rows = self._get_json(
                "/api/v3/klines",
                {
                    "symbol": symbol,
                    "interval": interval,
                    "startTime": cursor,
                    "endTime": end_ms,
                    "limit": 1000,
                },
            )
            if not rows:
                break
            for row in rows:
                close_time = int(row[6])
                if close_time > end_ms:
                    continue
                candles.append(
                    Candle(
                        symbol=symbol,
                        open_time=int(row[0]),
                        open=float(row[1]),
                        high=float(row[2]),
                        low=float(row[3]),
                        close=float(row[4]),
                        volume=float(row[5]),
                        close_time=close_time,
                        quote_volume=float(row[7]),
                    )
                )
            next_cursor = int(rows[-1][6]) + 1
            if next_cursor <= cursor:
                break
            cursor = next_cursor
            time.sleep(self.pause_seconds)
        deduped = {candle.open_time: candle for candle in candles}
        return [deduped[key] for key in sorted(deduped)]
