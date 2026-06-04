import unittest

from anomaly_tracker.candidates import apply_confirmation_bonus, cooldown_key, dedupe_candidates_by_symbol
from anomaly_tracker.models import AssetCalibration, ScoredRow, SignalCandidate, Thresholds


def _candidate(symbol="BTCUSDT", score=5.0, lane="main", interval="4h", direction="up"):
    return SignalCandidate(
        symbol=symbol,
        open_time=1,
        close=100.0,
        pct_change=2.0,
        score=score,
        level="signal",
        direction=direction,
        global_rank=1,
        reason="hacimli alim",
        source_interval=interval,
        lane=lane,
    )


class CandidateHelperTests(unittest.TestCase):
    def test_cooldown_key_includes_lane(self):
        main = _candidate(lane="main")
        fast = _candidate(lane="fast", interval="1h")

        self.assertEqual(cooldown_key(main), "BTCUSDT|main")
        self.assertEqual(cooldown_key(fast), "BTCUSDT|fast")
        self.assertNotEqual(cooldown_key(main), cooldown_key(fast))

    def test_dedupe_keeps_highest_score_per_symbol(self):
        main = _candidate(score=4.0, lane="main")
        fast = _candidate(score=6.5, lane="fast", interval="1h")

        result = dedupe_candidates_by_symbol([main, fast])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].symbol, "BTCUSDT")
        self.assertEqual(result[0].score, 6.5)
        self.assertEqual(result[0].lane, "fast")

    def test_confirmation_bonus_adds_score_when_same_direction_signal_exists(self):
        calibration = AssetCalibration(
            symbol="BTCUSDT",
            thresholds=Thresholds(watch=1.0, signal=2.0, critical=3.0),
            rows=[
                ScoredRow(
                    symbol="BTCUSDT",
                    open_time=1,
                    close=100.0,
                    pct_change=2.0,
                    score=3.0,
                    level="signal",
                    direction="up",
                    return_z=4.0,
                    volume_ratio=2.5,
                    range_ratio=1.5,
                    breakout=False,
                    reason="hacimli alim",
                )
            ],
        )
        candidate = _candidate(score=4.0)

        boosted = apply_confirmation_bonus([candidate], {"1h": [calibration]}, bonus=0.8)

        self.assertEqual(boosted[0].score, 4.8)
        self.assertIn("onay", boosted[0].reason)


if __name__ == "__main__":
    unittest.main()