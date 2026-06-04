import unittest

from anomaly_tracker.models import Candle, MarketContext, SignalCandidate
from anomaly_tracker.scoring import calibrate_asset, market_filter_decision, select_signal_candidates


def candle(i, close, volume=1_000_000, high=None, low=None):
    open_price = close if i == 0 else close / 1.001
    return Candle(
        symbol="TESTUSDT",
        open_time=i * 14_400_000,
        close_time=(i + 1) * 14_400_000 - 1,
        open=open_price,
        high=high if high is not None else max(open_price, close) * 1.002,
        low=low if low is not None else min(open_price, close) * 0.998,
        close=close,
        volume=volume,
        quote_volume=volume * close,
    )


class ScoringTests(unittest.TestCase):
    def test_calibrates_asset_specific_thresholds_and_flags_spike(self):
        candles = [candle(i, 100 + i * 0.05, 1_000_000) for i in range(70)]
        candles.append(candle(70, 108, 8_000_000, high=110, low=100))

        result = calibrate_asset("TESTUSDT", candles, rolling_bars=24)

        self.assertEqual(result.symbol, "TESTUSDT")
        self.assertGreater(result.thresholds.watch, 0)
        self.assertGreater(result.thresholds.signal, result.thresholds.watch)
        self.assertGreater(result.thresholds.critical, result.thresholds.signal)
        self.assertEqual(result.rows[-1].level, "critical")
        self.assertGreater(result.rows[-1].score, result.thresholds.critical)
        self.assertIn("hacimli alım", result.rows[-1].reason.lower())
        self.assertGreater(result.rows[-1].quote_volume, 0)

    def test_global_candidates_require_asset_signal_and_rank_limit(self):
        asset_a = [candle(i, 100 + i * 0.03, 1_000_000) for i in range(70)]
        asset_a.append(candle(70, 111, 9_000_000, high=112, low=100))

        asset_b = [candle(i, 50 + i * 0.02, 1_000_000) for i in range(70)]
        asset_b.append(candle(70, 53, 3_000_000, high=53.5, low=50))

        scored_a = calibrate_asset("AAAUSDT", asset_a, rolling_bars=24)
        scored_b = calibrate_asset("BBBUSDT", asset_b, rolling_bars=24)

        candidates = select_signal_candidates([scored_a, scored_b], global_limit=1)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].symbol, "AAAUSDT")
        self.assertEqual(candidates[0].global_rank, 1)
        self.assertGreaterEqual(candidates[0].score, scored_a.thresholds.signal)
        self.assertGreater(candidates[0].quote_volume, 0)

    def test_global_candidates_do_not_emit_stale_historical_signal(self):
        candles = [candle(i, 100 + i * 0.03, 1_000_000) for i in range(70)]
        candles.append(candle(70, 112, 9_000_000, high=113, low=100))
        for i in range(71, 80):
            candles.append(candle(i, 112 + (i - 70) * 0.02, 1_000_000))

        scored = calibrate_asset("STALEUSDT", candles, rolling_bars=24)

        self.assertEqual(select_signal_candidates([scored], global_limit=5), [])

    def test_market_filter_suppresses_weak_bullish_signal_in_risk_off(self):
        candidate = SignalCandidate(
            symbol="ALTUSDT",
            open_time=1,
            close=10.0,
            pct_change=2.1,
            score=3.5,
            level="signal",
            direction="up",
            global_rank=1,
            reason="hacimli alim",
        )
        context = MarketContext(
            reference_symbol="BTCUSDT",
            pct_change=-3.2,
            direction="down",
            mode="risk_off",
            reason="BTCUSDT -3.20%",
        )

        decision = market_filter_decision(candidate, context)

        self.assertFalse(decision["keep"])
        self.assertEqual(decision["reason"], "risk_off_weak_bullish")

    def test_market_filter_keeps_critical_bullish_signal_in_risk_off(self):
        candidate = SignalCandidate(
            symbol="ALTUSDT",
            open_time=1,
            close=10.0,
            pct_change=8.0,
            score=7.0,
            level="critical",
            direction="up",
            global_rank=1,
            reason="hacimli alim",
        )
        context = MarketContext(
            reference_symbol="BTCUSDT",
            pct_change=-3.2,
            direction="down",
            mode="risk_off",
            reason="BTCUSDT -3.20%",
        )

        decision = market_filter_decision(candidate, context)

        self.assertTrue(decision["keep"])
        self.assertEqual(decision["reason"], "critical_override")


if __name__ == "__main__":
    unittest.main()
