from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from anomaly_tracker.runner import run_scan
from anomaly_tracker.runtime import AppConfig


def health_payload(config: AppConfig) -> dict:
    return {
        "status": "ok",
        "symbol_limit": config.symbol_limit,
        "global_limit": config.global_limit,
        "interval": config.interval,
        "lookback_days": config.lookback_days,
        "min_history_days": config.min_history_days,
        "scan_interval_seconds": config.scan_interval_seconds,
        "scan_workers": config.scan_workers,
        "fast_lane_enabled": config.fast_lane_enabled,
        "fast_interval": config.fast_interval,
        "run_on_start": config.run_on_start,
        "telegram_configured": bool(config.telegram_bot_token and config.telegram_chat_id),
    }


class ScanState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_result: dict | None = None
        self.last_error: str | None = None
        self.running = False


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_latest_signals(output_dir: Path) -> dict:
    path = output_dir / "latest_crypto_signals.json"
    if not path.exists():
        return {"candidate_count": 0, "sendable_count": 0, "candidates": [], "sendable": []}
    return json.loads(path.read_text(encoding="utf-8"))


def _run_scan_locked(config: AppConfig, state: ScanState, send_telegram: bool) -> dict:
    with state.lock:
        if state.running:
            return {"status": "already_running"}
        state.running = True
    try:
        result = run_scan(config, send_telegram=send_telegram)
        with state.lock:
            state.last_result = result
            state.last_error = None
        return result
    except Exception as exc:
        with state.lock:
            state.last_error = str(exc)
        raise
    finally:
        with state.lock:
            state.running = False


def make_handler(config: AppConfig, state: ScanState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                payload = health_payload(config)
                with state.lock:
                    payload["running"] = state.running
                    payload["last_error"] = state.last_error
                _json_response(self, 200, payload)
                return
            if parsed.path == "/signals":
                _json_response(self, 200, _read_latest_signals(config.output_dir))
                return
            _json_response(self, 200, {"service": "crypto-anomaly-tracker", "routes": ["/health", "/signals", "POST /scan"]})

        def do_POST(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path != "/scan":
                _json_response(self, 404, {"error": "not_found"})
                return
            params = parse_qs(parsed.query)
            send = params.get("send", ["0"])[0] in {"1", "true", "yes"}
            try:
                _json_response(self, 200, _run_scan_locked(config, state, send_telegram=send))
            except Exception as exc:
                _json_response(self, 500, {"error": str(exc)})

    return Handler


def start_scheduler(config: AppConfig, state: ScanState) -> threading.Thread:
    def loop() -> None:
        if config.run_on_start:
            try:
                _run_scan_locked(config, state, send_telegram=True)
            except Exception:
                pass
        while True:
            time.sleep(config.scan_interval_seconds)
            try:
                _run_scan_locked(config, state, send_telegram=True)
            except Exception:
                pass

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


def serve(config: AppConfig | None = None) -> None:
    active_config = config or AppConfig.from_env()
    active_config.output_dir.mkdir(parents=True, exist_ok=True)
    state = ScanState()
    start_scheduler(active_config, state)
    server = ThreadingHTTPServer(("0.0.0.0", active_config.port), make_handler(active_config, state))
    server.serve_forever()
