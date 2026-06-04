import unittest

from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.service import ScanState, dashboard_html, handle_telegram_update, health_payload, summary_payload


class ServiceTests(unittest.TestCase):
    def test_health_payload_exposes_safe_operational_config(self):
        config = AppConfig.from_env(
            {
                "PORT": "8081",
                "ANOMALY_SYMBOL_LIMIT": "12",
                "ANOMALY_GLOBAL_LIMIT": "3",
                "ANOMALY_RUN_ON_START": "true",
                "TELEGRAM_BOT_TOKEN": "secret",
                "TELEGRAM_USER_ID": "42",
            }
        )

        payload = health_payload(config)

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["symbol_limit"], 12)
        self.assertEqual(payload["global_limit"], 3)
        self.assertTrue(payload["telegram_configured"])
        self.assertNotIn("secret", str(payload))

    def test_scan_state_records_success_error_and_next_due_metadata(self):
        state = ScanState()

        state.record_start(now=100.0)
        state.record_success(
            {
                "candidate_count": 2,
                "sendable_count": 1,
                "suppressed_count": 1,
                "sent_symbols": ["BTCUSDT"],
            },
            now=130.5,
        )
        state.mark_next_due(200.0)

        self.assertFalse(state.running)
        self.assertEqual(state.scan_count, 1)
        self.assertEqual(state.success_count, 1)
        self.assertEqual(state.failure_count, 0)
        self.assertEqual(state.last_scan_duration_seconds, 30.5)
        self.assertEqual(state.last_result_summary["candidate_count"], 2)
        self.assertEqual(state.next_scan_due_at, "1970-01-01T00:03:20Z")

        state.record_start(now=220.0)
        state.record_error(ValueError("boom"), now=225.0)

        self.assertEqual(state.scan_count, 2)
        self.assertEqual(state.failure_count, 1)
        self.assertEqual(state.last_error, "boom")
        self.assertEqual(state.recent_runs[-1]["status"], "error")

    def test_health_payload_includes_scan_lifecycle_when_state_is_provided(self):
        config = AppConfig.from_env({"TELEGRAM_USER_ID": "42"})
        state = ScanState()
        state.record_start(now=100.0)
        state.record_success({"candidate_count": 0, "sendable_count": 0}, now=101.25)

        payload = health_payload(config, state)

        self.assertFalse(payload["running"])
        self.assertEqual(payload["scan_count"], 1)
        self.assertEqual(payload["success_count"], 1)
        self.assertEqual(payload["last_scan_duration_seconds"], 1.25)
        self.assertEqual(payload["last_success_at"], "1970-01-01T00:01:41Z")
        self.assertEqual(payload["last_result_summary"]["candidate_count"], 0)

    def test_summary_payload_combines_health_and_signals(self):
        config = AppConfig.from_env({"TELEGRAM_USER_ID": "42"})
        state = ScanState()
        signals = {"candidate_count": 1, "sendable_count": 1, "candidates": [{"symbol": "BTCUSDT"}]}

        payload = summary_payload(config, state, signals)

        self.assertEqual(payload["health"]["status"], "ok")
        self.assertEqual(payload["signals"]["candidate_count"], 1)
        self.assertNotIn("secret", str(payload))

    def test_dashboard_html_renders_safe_signal_cards(self):
        health = {"status": "ok", "running": False, "last_error": None}
        signals = {
            "candidate_count": 1,
            "sendable_count": 1,
            "suppressed_count": 0,
            "market_context": {"mode": "risk_off", "reference_symbol": "BTCUSDT"},
            "candidates": [
                {
                    "symbol": "BTCUSDT",
                    "message": "BTC | $100 | 4s +2.00%\nSebep: hacimli alim",
                    "send_decision": {"send": True, "reason": "first_signal"},
                }
            ],
        }

        html = dashboard_html(health, signals)

        self.assertIn("crypto-anomaly-tracker", html)
        self.assertIn("BTCUSDT", html)
        self.assertIn("risk_off", html)
        self.assertIn("first_signal", html)
        self.assertIn("Hacimli", html)

    def test_handle_telegram_update_replies_to_allowed_chat_and_starts_scan(self):
        config = AppConfig.from_env(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "TELEGRAM_USER_ID": "42",
                "ANOMALY_PUBLIC_BASE_URL": "https://radar.example",
            }
        )
        state = ScanState()
        sent = []
        scans = []
        update = {"message": {"chat": {"id": 42}, "text": "/scan"}}

        handled = handle_telegram_update(
            config,
            state,
            update,
            read_signals=lambda: {"candidate_count": 0, "candidates": []},
            send=lambda chat_id, text: sent.append((chat_id, text)),
            start_scan=lambda: scans.append(True),
        )

        self.assertTrue(handled)
        self.assertEqual(scans, [True])
        self.assertEqual(sent[0][0], "42")
        self.assertIn("başlatıyorum", sent[0][1])

    def test_handle_telegram_update_ignores_other_chats(self):
        config = AppConfig.from_env({"TELEGRAM_BOT_TOKEN": "token", "TELEGRAM_USER_ID": "42"})
        state = ScanState()
        sent = []
        update = {"message": {"chat": {"id": 99}, "text": "/status"}}

        handled = handle_telegram_update(
            config,
            state,
            update,
            read_signals=lambda: {"candidate_count": 0, "candidates": []},
            send=lambda chat_id, text: sent.append((chat_id, text)),
            start_scan=lambda: None,
        )

        self.assertFalse(handled)
        self.assertEqual(sent, [])

if __name__ == "__main__":
    unittest.main()
