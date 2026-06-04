import unittest

from anomaly_tracker.models import SignalCandidate
from anomaly_tracker.outputs import candidate_to_message, candidates_to_jsonable


class OutputTests(unittest.TestCase):
    def test_candidate_to_message_is_readable_telegram_card(self):
        candidate = SignalCandidate(
            symbol="HOMEUSDT",
            open_time=1_780_000_000_000,
            close=0.0506,
            pct_change=36.89,
            score=6.2,
            level="critical",
            direction="up",
            global_rank=1,
            reason="hacimli alim, genis mum",
            source_interval="4h",
            quote_volume=13_800_000,
        )

        message = candidate_to_message(candidate)

        self.assertEqual(
            message,
            "\n".join(
                [
                    "🚨 KRİTİK SİNYAL | HOME",
                    "Fiyat: $0.0506 | 4s: +36.89%",
                    "Yön: Alım | Sıra: #1 | Skor: 6.20",
                    "Neden: hacimli alım, geniş mum",
                    "Hacim: $13.8M",
                ]
            ),
        )
        self.assertIn("$0.0506", message)
        self.assertNotIn("Onem", message)
        self.assertNotIn("Yon", message)
        self.assertNotIn("genis", message)

    def test_candidate_to_message_marks_fast_lane_on_first_line(self):
        candidate = SignalCandidate(
            symbol="BTCUSDT",
            open_time=1_780_000_000_000,
            close=109250.0,
            pct_change=2.4,
            score=5.3,
            level="signal",
            direction="up",
            global_rank=1,
            reason="hacimli alim, band kirilimi",
            source_interval="1h",
            lane="fast",
            quote_volume=12_400_000,
        )

        message = candidate_to_message(candidate)

        self.assertEqual(message.splitlines()[0], "⚡ HIZLI SİNYAL | BTC")
        self.assertIn("Yön: Alım", message)
        self.assertIn("Hacim: $12.4M", message)

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
            quote_volume=850_000,
        )

        payload = candidates_to_jsonable([candidate])

        self.assertEqual(payload[0]["symbol"], "ETHUSDT")
        self.assertEqual(payload[0]["global_rank"], 2)
        self.assertEqual(payload[0]["reason"], "Fiyat dustu.")
        self.assertEqual(payload[0]["quote_volume"], 850_000)


if __name__ == "__main__":
    unittest.main()
