import json
import tempfile
import unittest
from pathlib import Path

from anomaly_tracker.models import AssetCalibration, ScoredRow, SignalCandidate, Thresholds
from anomaly_tracker.runner import persist_scan_result


class RunnerTests(unittest.TestCase):
    def test_persist_scan_result_writes_latest_files(self):
        calibration = AssetCalibration(
            symbol="BTCUSDT",
            thresholds=Thresholds(watch=1.0, signal=2.0, critical=3.0),
            rows=[
                ScoredRow(
                    symbol="BTCUSDT",
                    open_time=1,
                    close=100.0,
                    pct_change=2.0,
                    score=3.2,
                    level="critical",
                    direction="up",
                    return_z=5.0,
                    volume_ratio=2.0,
                    range_ratio=2.0,
                    breakout=True,
                    reason="Hacim canlandi.",
                )
            ],
        )
        candidate = SignalCandidate(
            symbol="BTCUSDT",
            open_time=1,
            close=100.0,
            pct_change=2.0,
            score=3.2,
            level="critical",
            direction="up",
            global_rank=1,
            reason="Hacim canlandi.",
        )
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            persist_scan_result(output_dir, [calibration], [candidate], [candidate], ["BTCUSDT"], "4h", 30)

            payload = json.loads((output_dir / "latest_crypto_signals.json").read_text())
            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(payload["sendable_count"], 1)
            self.assertEqual(payload["symbols_scanned"], ["BTCUSDT"])
            self.assertTrue((output_dir / "latest_crypto_scan.md").exists())


if __name__ == "__main__":
    unittest.main()
