import json
import unittest
from unittest.mock import MagicMock, patch

from anomaly_tracker.binance import BinanceClient


class BinanceClientTests(unittest.TestCase):
    def test_retries_on_rate_limit_then_succeeds(self):
        client = BinanceClient(pause_seconds=0)
        responses = [
            _http_error(429),
            json.dumps({"serverTime": 123}).encode("utf-8"),
        ]
        call_count = {"n": 0}

        def fake_urlopen(request, timeout=30):
            index = call_count["n"]
            call_count["n"] += 1
            if index == 0:
                raise responses[0]
            body = responses[1]
            mock_response = MagicMock()
            mock_response.read.return_value = body
            mock_response.__enter__.return_value = mock_response
            mock_response.__exit__.return_value = None
            return mock_response

        with patch("anomaly_tracker.binance.time.sleep"), patch(
            "anomaly_tracker.binance.urllib.request.urlopen", side_effect=fake_urlopen
        ):
            self.assertEqual(client.server_time_ms(), 123)
        self.assertEqual(call_count["n"], 2)


def _http_error(code: int):
    import urllib.error

    return urllib.error.HTTPError("https://api.binance.com", code, "rate", None, None)


if __name__ == "__main__":
    unittest.main()