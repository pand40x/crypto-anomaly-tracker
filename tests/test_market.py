import unittest

from anomaly_tracker.market import combined_market_context, market_context_from_calibrations
from anomaly_tracker.models import AssetCalibration, ScoredRow, Thresholds


class MarketTests(unittest.TestCase):
    def _calibration(self, symbol: str, pct_change: float) -> AssetCalibration:
        return AssetCalibration(
            symbol=symbol,
            thresholds=Thresholds(1.0, 2.0, 3.0),
            rows=[
                ScoredRow(
                    symbol=symbol,
                    open_time=1,
                    close=100.0,
                    pct_change=pct_change,
                    score=3.0,
                    level="signal",
                    direction="down" if pct_change < 0 else "up",
                    return_z=2.0,
                    volume_ratio=2.0,
                    range_ratio=1.5,
                    breakout=False,
                    reason="test",
                )
            ],
        )

    def test_combined_market_context_risk_off_if_any_reference_risk_off(self):
        calibrations = [
            self._calibration("BTCUSDT", -3.0),
            self._calibration("ETHUSDT", 1.0),
        ]
        context = combined_market_context(calibrations, ["BTCUSDT", "ETHUSDT"], -2.5, 2.5)
        self.assertEqual(context.mode, "risk_off")

    def test_market_context_from_calibrations_detects_risk_off(self):
        context = market_context_from_calibrations([self._calibration("BTCUSDT", -3.2)], "BTCUSDT", -2.5, 2.5)
        self.assertEqual(context.mode, "risk_off")


if __name__ == "__main__":
    unittest.main()