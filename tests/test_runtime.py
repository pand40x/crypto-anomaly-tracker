import json
import os
import tempfile
import unittest
from pathlib import Path

from anomaly_tracker.models import SignalCandidate
from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.state import CooldownState
from anomaly_tracker.telegram import build_send_message_payload


def candidate(symbol="BTCUSDT", score=5.0, open_time=1_000_000):
    return SignalCandidate(
        symbol=symbol,
        open_time=open_time,
        close=100_000.0,
        pct_change=2.0,
        score=score,
        level="signal",
        direction="up",
        global_rank=1,
        reason="Hacim canlandi.",
    )


class RuntimeTests(unittest.TestCase):
    def test_config_reads_environment_with_defaults(self):
        env = {
            "PORT": "8090",
            "ANOMALY_SYMBOL_LIMIT": "25",
            "ANOMALY_LOOKBACK_DAYS": "365",
            "ANOMALY_MIN_HISTORY_DAYS": "180",
            "ANOMALY_SCAN_INTERVAL_SECONDS": "60",
            "ANOMALY_SCAN_WORKERS": "6",
            "ANOMALY_FAST_LANE_ENABLED": "true",
            "ANOMALY_FAST_INTERVAL": "1h",
            "ANOMALY_FAST_MIN_VOLUME_RATIO": "3.0",
            "ANOMALY_RUN_ON_START": "false",
            "TELEGRAM_USER_ID": "12345",
        }

        config = AppConfig.from_env(env)

        self.assertEqual(config.port, 8090)
        self.assertEqual(config.symbol_limit, 25)
        self.assertEqual(config.lookback_days, 365)
        self.assertEqual(config.min_history_days, 180)
        self.assertEqual(config.scan_interval_seconds, 60)
        self.assertEqual(config.scan_workers, 6)
        self.assertTrue(config.fast_lane_enabled)
        self.assertEqual(config.fast_interval, "1h")
        self.assertEqual(config.fast_min_volume_ratio, 3.0)
        self.assertFalse(config.run_on_start)
        self.assertEqual(config.telegram_chat_id, "12345")
        self.assertTrue(config.market_filter_enabled)
        self.assertEqual(config.market_reference_symbol, "BTCUSDT")
        self.assertEqual(config.market_risk_off_pct_change, -2.5)
        self.assertEqual(config.market_risk_on_pct_change, 2.5)

    def test_config_reads_market_filter_overrides(self):
        config = AppConfig.from_env(
            {
                "ANOMALY_MARKET_FILTER_ENABLED": "false",
                "ANOMALY_MARKET_REFERENCE_SYMBOL": "ETHUSDT",
                "ANOMALY_MARKET_RISK_OFF_PCT_CHANGE": "-4.0",
                "ANOMALY_MARKET_RISK_ON_PCT_CHANGE": "4.0",
            }
        )

        self.assertFalse(config.market_filter_enabled)
        self.assertEqual(config.market_reference_symbol, "ETHUSDT")
        self.assertEqual(config.market_risk_off_pct_change, -4.0)
        self.assertEqual(config.market_risk_on_pct_change, 4.0)

    def test_cooldown_allows_stronger_resignal_inside_window(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = CooldownState(Path(tmp) / "state.json", cooldown_seconds=12 * 3600)

            first = candidate(score=5.0, open_time=1000)
            same = candidate(score=5.2, open_time=2000)
            stronger = candidate(score=5.8, open_time=3000)

            self.assertTrue(state.should_send(first))
            state.record_sent(first)
            self.assertFalse(state.should_send(same))
            self.assertTrue(state.should_send(stronger))

    def test_cooldown_explains_first_suppressed_and_stronger_decisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = CooldownState(Path(tmp) / "state.json", cooldown_seconds=12 * 3600)

            first = candidate(score=5.0, open_time=1000)
            same = candidate(score=5.2, open_time=2000)
            stronger = candidate(score=5.8, open_time=3000)

            self.assertEqual(state.send_decision(first)["reason"], "first_signal")
            self.assertTrue(state.send_decision(first)["send"])
            state.record_sent(first)

            same_decision = state.send_decision(same)
            self.assertFalse(same_decision["send"])
            self.assertEqual(same_decision["reason"], "cooldown")
            self.assertEqual(same_decision["previous_score"], 5.0)

            stronger_decision = state.send_decision(stronger)
            self.assertTrue(stronger_decision["send"])
            self.assertEqual(stronger_decision["reason"], "stronger_signal")

    def test_cooldown_persists_state_to_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            state = CooldownState(path, cooldown_seconds=12 * 3600)
            state.record_sent(candidate(symbol="ETHUSDT", score=6.0, open_time=5000))

            payload = json.loads(path.read_text())

            self.assertEqual(payload["ETHUSDT"]["last_score"], 6.0)
            self.assertEqual(payload["ETHUSDT"]["last_open_time"], 5000)

    def test_telegram_payload_uses_chat_id_and_markdown_disabled(self):
        payload = build_send_message_payload("99", "hello")

        self.assertEqual(payload["chat_id"], "99")
        self.assertEqual(payload["text"], "hello")
        self.assertNotIn("parse_mode", payload)


if __name__ == "__main__":
    unittest.main()
