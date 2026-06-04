import unittest

from anomaly_tracker.models import SignalCandidate
from anomaly_tracker.sectors import detect_sector_heat, sector_for_symbol


def _candidate(symbol: str, direction: str = "up", score: float = 4.0):
    return SignalCandidate(
        symbol=symbol,
        open_time=1,
        close=1.0,
        pct_change=2.0,
        score=score,
        level="signal",
        direction=direction,
        global_rank=1,
        reason="test",
    )


class SectorTests(unittest.TestCase):
    def test_sector_mapping(self):
        self.assertEqual(sector_for_symbol("FETUSDT"), "ai")
        self.assertEqual(sector_for_symbol("PEPEUSDT"), "meme")

    def test_detect_sector_heat_requires_min_count(self):
        candidates = [
            _candidate("FETUSDT"),
            _candidate("RENDERUSDT"),
            _candidate("TAOUSDT"),
        ]
        heats = detect_sector_heat(candidates, min_count=3, min_avg_score=2.0)
        self.assertEqual(len(heats), 1)
        self.assertEqual(heats[0].sector_id, "ai")
        self.assertEqual(heats[0].count, 3)


if __name__ == "__main__":
    unittest.main()