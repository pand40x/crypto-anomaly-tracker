import unittest

from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.service import health_payload


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


if __name__ == "__main__":
    unittest.main()
