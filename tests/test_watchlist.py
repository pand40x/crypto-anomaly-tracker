import tempfile
import unittest
from pathlib import Path

from anomaly_tracker.models import SignalCandidate
from anomaly_tracker.watchlist import WatchlistStore, watchlist_send_override


class WatchlistTests(unittest.TestCase):
    def test_add_remove_and_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = WatchlistStore(Path(tmp) / "watchlist.json")
            entry = store.add("btc", tags=["core", "ai"])
            self.assertEqual(entry.symbol, "BTCUSDT")
            self.assertEqual(entry.tags, ("ai", "core"))
            self.assertEqual(store.symbols(), ["BTCUSDT"])
            self.assertTrue(store.remove("BTC"))
            self.assertEqual(store.symbols(), [])

    def test_instant_override_sends_despite_cooldown(self):
        with tempfile.TemporaryDirectory() as tmp:
            entry = WatchlistStore(Path(tmp) / "watchlist.json").add(
                "ETH", alert_mode="instant", min_level="signal"
            )
            candidate = SignalCandidate(
                symbol="ETHUSDT",
                open_time=1,
                close=1.0,
                pct_change=2.0,
                score=3.0,
                level="signal",
                direction="up",
                global_rank=1,
                reason="test",
            )
            decision = watchlist_send_override(entry, "signal", False, "cooldown")
            self.assertTrue(decision["send"])
            self.assertEqual(decision["reason"], "watchlist_instant_override")


if __name__ == "__main__":
    unittest.main()