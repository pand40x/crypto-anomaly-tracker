import unittest

from anomaly_tracker.telegram_commands import (
    build_signals_message,
    build_status_message,
    command_response,
    normalize_command,
)


class TelegramCommandTests(unittest.TestCase):
    def test_normalize_command_accepts_mentions_and_aliases(self):
        self.assertEqual(normalize_command("/status@panda0x001_bot"), ("/status", []))
        self.assertEqual(normalize_command("/durum"), ("/status", []))
        self.assertEqual(normalize_command("/sinyaller"), ("/signals", []))
        self.assertEqual(normalize_command("/izle BTC ai"), ("/watch_add", ["BTC", "ai"]))
        self.assertEqual(normalize_command("selam"), (None, []))

    def test_status_message_is_product_like_and_safe(self):
        text = build_status_message(
            {
                "running": False,
                "last_error": None,
                "last_scan_duration_seconds": 222.441,
                "last_result_summary": {
                    "candidate_count": 2,
                    "sendable_count": 0,
                    "suppressed_count": 2,
                    "filtered_count": 0,
                    "sent_symbols": [],
                },
                "market_reference_symbol": "BTCUSDT",
            }
        )

        self.assertIn("Panda Anomali Radarı", text)
        self.assertIn("Durum: Hazır", text)
        self.assertIn("Son tarama: 222.4 sn", text)
        self.assertIn("Aday: 2", text)
        self.assertNotIn("secret", text.lower())

    def test_signals_message_summarizes_latest_candidates(self):
        text = build_signals_message(
            {
                "candidate_count": 1,
                "sendable_count": 1,
                "suppressed_count": 0,
                "filtered_count": 0,
                "market_context": {"reference_symbol": "BTCUSDT", "mode": "neutral", "pct_change": -0.42},
                "candidates": [
                    {
                        "symbol": "ZROUSDT",
                        "message": "🚨 KRİTİK SİNYAL | ZRO\nFiyat: $1.067 | 1s: -5.83%",
                        "send_decision": {"send": True, "reason": "first_signal"},
                    }
                ],
            }
        )

        self.assertIn("Son Sinyaller", text)
        self.assertIn("BTCUSDT: neutral (-0.42%)", text)
        self.assertIn("ZRO", text)
        self.assertIn("first_signal", text)

    def test_command_response_routes_scan_status_signals_and_dashboard(self):
        health = {"running": False, "last_error": None, "last_result_summary": {"candidate_count": 0}}
        signals = {"candidate_count": 0, "candidates": []}

        text, action = command_response("/scan", health, signals, "https://radar.example")
        self.assertEqual(action, "scan")
        self.assertIn("başlatıyorum", text)

        text, action = command_response("/status", health, signals, "https://radar.example")
        self.assertIsNone(action)
        self.assertIn("Panda Anomali Radarı", text)

        text, action = command_response("/dashboard", health, signals, "https://radar.example")
        self.assertIsNone(action)
        self.assertIn("https://radar.example/dashboard", text)


if __name__ == "__main__":
    unittest.main()
