import json
import tempfile
import unittest
from pathlib import Path

from anomaly_tracker.models import AssetCalibration, MarketContext, ScoredRow, SignalCandidate, Thresholds
from anomaly_tracker.runner import (
    apply_market_filter,
    candidate_decision_key,
    market_context_from_calibrations,
    persist_scan_result,
)


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

            send_decisions = {
                candidate_decision_key(candidate): {
                    "send": True,
                    "reason": "first_signal",
                }
            }

            persist_scan_result(
                output_dir,
                [calibration],
                [candidate],
                [candidate],
                [],
                send_decisions,
                [],
                {},
                None,
                ["BTCUSDT"],
                "4h",
                30,
            )

            payload = json.loads((output_dir / "latest_crypto_signals.json").read_text())
            self.assertEqual(payload["candidate_count"], 1)
            self.assertEqual(payload["sendable_count"], 1)
            self.assertEqual(payload["suppressed_count"], 0)
            self.assertEqual(payload["symbols_scanned"], ["BTCUSDT"])
            self.assertEqual(payload["candidates"][0]["send_decision"]["reason"], "first_signal")
            self.assertTrue((output_dir / "latest_crypto_scan.md").exists())

    def test_persist_scan_result_writes_suppressed_candidates(self):
        sent = SignalCandidate(
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
        suppressed = SignalCandidate(
            symbol="ETHUSDT",
            open_time=1,
            close=2200.0,
            pct_change=1.2,
            score=2.4,
            level="signal",
            direction="up",
            global_rank=2,
            reason="Hacim canlandi.",
        )
        send_decisions = {
            candidate_decision_key(sent): {"send": True, "reason": "first_signal"},
            candidate_decision_key(suppressed): {
                "send": False,
                "reason": "cooldown",
                "previous_score": 2.3,
            },
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            persist_scan_result(
                output_dir,
                [],
                [sent, suppressed],
                [sent],
                [suppressed],
                send_decisions,
                [],
                {},
                None,
                ["BTCUSDT", "ETHUSDT"],
                "4h",
                30,
            )

            payload = json.loads((output_dir / "latest_crypto_signals.json").read_text())

            self.assertEqual(payload["candidate_count"], 2)
            self.assertEqual(payload["sendable_count"], 1)
            self.assertEqual(payload["suppressed_count"], 1)
            self.assertEqual(payload["suppressed"][0]["symbol"], "ETHUSDT")
            self.assertEqual(payload["suppressed"][0]["send_decision"]["reason"], "cooldown")
            self.assertEqual(payload["send_decisions"][candidate_decision_key(suppressed)]["send"], False)

    def test_market_context_from_calibrations_detects_risk_off(self):
        calibration = AssetCalibration(
            symbol="BTCUSDT",
            thresholds=Thresholds(1, 2, 3),
            rows=[
                ScoredRow(
                    symbol="BTCUSDT",
                    open_time=1,
                    close=100.0,
                    pct_change=-3.1,
                    score=4.0,
                    level="signal",
                    direction="down",
                    return_z=-4.0,
                    volume_ratio=2.0,
                    range_ratio=2.0,
                    breakout=True,
                    reason="hacimli satis",
                )
            ],
        )

        context = market_context_from_calibrations([calibration], "BTCUSDT", -2.5, 2.5)

        self.assertEqual(context.mode, "risk_off")
        self.assertEqual(context.reference_symbol, "BTCUSDT")
        self.assertEqual(context.pct_change, -3.1)

    def test_apply_market_filter_persists_filtered_candidates_and_reranks_kept(self):
        weak_bull = SignalCandidate(
            symbol="ALTUSDT",
            open_time=1,
            close=10.0,
            pct_change=2.1,
            score=5.0,
            level="signal",
            direction="up",
            global_rank=1,
            reason="hacimli alim",
        )
        strong_bull = SignalCandidate(
            symbol="MOONUSDT",
            open_time=1,
            close=1.0,
            pct_change=9.0,
            score=4.0,
            level="critical",
            direction="up",
            global_rank=2,
            reason="hacimli alim",
        )
        context = MarketContext(
            reference_symbol="BTCUSDT",
            pct_change=-3.1,
            direction="down",
            mode="risk_off",
            reason="BTCUSDT -3.10%",
        )

        kept, filtered, decisions = apply_market_filter([weak_bull, strong_bull], context, global_limit=10)

        self.assertEqual([item.symbol for item in kept], ["MOONUSDT"])
        self.assertEqual(kept[0].global_rank, 1)
        self.assertEqual([item.symbol for item in filtered], ["ALTUSDT"])
        self.assertEqual(decisions[candidate_decision_key(weak_bull)]["reason"], "risk_off_weak_bullish")

    def test_persist_scan_result_writes_market_filter_metadata(self):
        kept = SignalCandidate(
            symbol="MOONUSDT",
            open_time=1,
            close=1.0,
            pct_change=9.0,
            score=4.0,
            level="critical",
            direction="up",
            global_rank=1,
            reason="hacimli alim",
        )
        filtered = SignalCandidate(
            symbol="ALTUSDT",
            open_time=1,
            close=10.0,
            pct_change=2.1,
            score=5.0,
            level="signal",
            direction="up",
            global_rank=2,
            reason="hacimli alim",
        )
        context = MarketContext(
            reference_symbol="BTCUSDT",
            pct_change=-3.1,
            direction="down",
            mode="risk_off",
            reason="BTCUSDT -3.10%",
        )
        market_decisions = {
            candidate_decision_key(kept): {"keep": True, "reason": "critical_override"},
            candidate_decision_key(filtered): {"keep": False, "reason": "risk_off_weak_bullish"},
        }

        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            persist_scan_result(
                output_dir,
                [],
                [kept],
                [kept],
                [],
                {candidate_decision_key(kept): {"send": True, "reason": "first_signal"}},
                [filtered],
                market_decisions,
                context,
                ["MOONUSDT", "ALTUSDT"],
                "4h",
                30,
                raw_candidate_count=2,
            )

            payload = json.loads((output_dir / "latest_crypto_signals.json").read_text())

            self.assertEqual(payload["raw_candidate_count"], 2)
            self.assertEqual(payload["filtered_count"], 1)
            self.assertEqual(payload["market_context"]["mode"], "risk_off")
            self.assertEqual(payload["filtered"][0]["symbol"], "ALTUSDT")
            self.assertEqual(payload["filtered"][0]["market_filter_decision"]["reason"], "risk_off_weak_bullish")


if __name__ == "__main__":
    unittest.main()
