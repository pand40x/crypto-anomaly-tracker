import unittest

from anomaly_tracker.universe import select_top_usdt_symbols


class UniverseTests(unittest.TestCase):
    def test_selects_active_usdt_spot_symbols_by_quote_volume(self):
        exchange_info = {
            "symbols": [
                {"symbol": "BTCUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
                {"symbol": "ETHUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
                {"symbol": "OLDUSDT", "status": "BREAK", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
                {"symbol": "EURUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
                {"symbol": "BTCDOWNUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
                {"symbol": "BNBBTC", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "BTC"},
            ]
        }
        tickers = [
            {"symbol": "ETHUSDT", "quoteVolume": "200"},
            {"symbol": "BTCUSDT", "quoteVolume": "300"},
            {"symbol": "OLDUSDT", "quoteVolume": "10000"},
            {"symbol": "EURUSDT", "quoteVolume": "9000"},
            {"symbol": "BTCDOWNUSDT", "quoteVolume": "8000"},
            {"symbol": "BNBBTC", "quoteVolume": "7000"},
        ]

        symbols = select_top_usdt_symbols(exchange_info, tickers, limit=10)

        self.assertEqual(symbols, ["BTCUSDT", "ETHUSDT"])

    def test_applies_limit_after_filtering(self):
        exchange_info = {
            "symbols": [
                {"symbol": "AAAUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
                {"symbol": "BBBUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
                {"symbol": "CCCUSDT", "status": "TRADING", "isSpotTradingAllowed": True, "quoteAsset": "USDT"},
            ]
        }
        tickers = [
            {"symbol": "AAAUSDT", "quoteVolume": "10"},
            {"symbol": "BBBUSDT", "quoteVolume": "30"},
            {"symbol": "CCCUSDT", "quoteVolume": "20"},
        ]

        self.assertEqual(select_top_usdt_symbols(exchange_info, tickers, limit=2), ["BBBUSDT", "CCCUSDT"])


if __name__ == "__main__":
    unittest.main()
