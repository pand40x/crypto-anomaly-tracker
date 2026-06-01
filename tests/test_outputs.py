import unittest

from anomaly_tracker.models import SignalCandidate
from anomaly_tracker.outputs import candidate_to_message, candidates_to_jsonable


class OutputTests(unittest.TestCase):
    def test_candidate_to_message_is_human_readable(self):
        candidate = SignalCandidate(
            symbol="BTCUSDT",
            open_time=1_780_000_000_000,
            close=109250.0,
            pct_change=2.4,
            score=5.3,
            level="signal",
            direction="up",
            global_rank=1,
            reason="Hacim normale gore 2.1x canlandi. Fiyat son haftalik bandin disina tasti.",
            source_interval="1h",
            lane="fast",
        )

        message = candidate_to_message(candidate)

        self.assertIn("BTC", message)
        self.assertIn("son 1 saatte +2.40%", message)
        self.assertIn("$109,250", message)
        self.assertIn("erken uyari", message)
        self.assertIn("fast-lane", message)

    def test_candidates_to_jsonable_preserves_rank_and_reason(self):
        candidate = SignalCandidate(
            symbol="ETHUSDT",
            open_time=1,
            close=2200.0,
            pct_change=-3.1,
            score=6.2,
            level="critical",
            direction="down",
            global_rank=2,
            reason="Fiyat dustu.",
        )

        payload = candidates_to_jsonable([candidate])

        self.assertEqual(payload[0]["symbol"], "ETHUSDT")
        self.assertEqual(payload[0]["global_rank"], 2)
        self.assertEqual(payload[0]["reason"], "Fiyat dustu.")


if __name__ == "__main__":
    unittest.main()
