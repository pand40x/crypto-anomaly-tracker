import unittest

from anomaly_tracker.models import AssetCalibration, ScoredRow, Thresholds
from anomaly_tracker.runner import fast_lane_candidates


def row(symbol, level, score):
    return ScoredRow(
        symbol=symbol,
        open_time=1000,
        close=1.0,
        pct_change=4.0,
        score=score,
        level=level,
        direction="up",
        return_z=5.0,
        volume_ratio=5.0,
        range_ratio=3.0,
        breakout=True,
        reason="Hacim canlandi.",
    )


class FastLaneTests(unittest.TestCase):
    def test_fast_lane_only_promotes_latest_critical_rows(self):
        calibrations = [
            AssetCalibration("AAAUSDT", Thresholds(1, 2, 3), [row("AAAUSDT", "critical", 5.0)]),
            AssetCalibration("BBBUSDT", Thresholds(1, 2, 3), [row("BBBUSDT", "signal", 4.0)]),
        ]

        candidates = fast_lane_candidates(calibrations, global_limit=10)

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].symbol, "AAAUSDT")
        self.assertEqual(candidates[0].source_interval, "1h")
        self.assertEqual(candidates[0].lane, "fast")


if __name__ == "__main__":
    unittest.main()
