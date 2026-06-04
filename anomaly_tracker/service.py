from __future__ import annotations

import json
from datetime import datetime, timezone
from html import escape
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from anomaly_tracker.runner import run_scan
from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.telegram import get_updates, send_message
from anomaly_tracker.telegram_commands import command_response


def _iso_utc(timestamp: float | None) -> str | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _result_summary(result: dict | None) -> dict | None:
    if result is None:
        return None
    return {
        "candidate_count": result.get("candidate_count", 0),
        "sendable_count": result.get("sendable_count", 0),
        "suppressed_count": result.get("suppressed_count", 0),
        "filtered_count": result.get("filtered_count", 0),
        "sent_symbols": result.get("sent_symbols", []),
    }


def health_payload(config: AppConfig, state: "ScanState | None" = None) -> dict:
    payload = {
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
        "market_filter_enabled": config.market_filter_enabled,
        "market_reference_symbol": config.market_reference_symbol,
        "telegram_configured": bool(config.telegram_bot_token and config.telegram_chat_id),
        "telegram_commands_enabled": bool(
            config.telegram_commands_enabled and config.telegram_bot_token and config.telegram_chat_id
        ),
    }
    if state is not None:
        payload.update(state.snapshot())
    return payload


class ScanState:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.last_result: dict | None = None
        self.last_error: str | None = None
        self.running = False
        self.current_scan_started_at: str | None = None
        self.last_scan_started_at: str | None = None
        self.last_scan_finished_at: str | None = None
        self.last_scan_duration_seconds: float | None = None
        self.last_success_at: str | None = None
        self.last_error_at: str | None = None
        self.next_scan_due_at: str | None = None
        self.scan_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_result_summary: dict | None = None
        self.recent_runs: list[dict] = []

    def record_start(self, now: float | None = None) -> None:
        active_now = time.time() if now is None else now
        started_at = _iso_utc(active_now)
        self.running = True
        self.scan_count += 1
        self.current_scan_started_at = started_at
        self.last_scan_started_at = started_at

    def record_success(self, result: dict, now: float | None = None) -> None:
        active_now = time.time() if now is None else now
        started_ts = _parse_iso_utc(self.current_scan_started_at)
        duration = round(active_now - started_ts, 3) if started_ts is not None else None
        finished_at = _iso_utc(active_now)
        self.running = False
        self.success_count += 1
        self.last_result = result
        self.last_error = None
        self.last_scan_finished_at = finished_at
        self.last_scan_duration_seconds = duration
        self.last_success_at = finished_at
        self.current_scan_started_at = None
        self.last_result_summary = _result_summary(result)
        self._append_recent_run("success", finished_at, duration, self.last_result_summary, None)

    def record_error(self, error: Exception, now: float | None = None) -> None:
        active_now = time.time() if now is None else now
        started_ts = _parse_iso_utc(self.current_scan_started_at)
        duration = round(active_now - started_ts, 3) if started_ts is not None else None
        finished_at = _iso_utc(active_now)
        self.running = False
        self.failure_count += 1
        self.last_error = str(error)
        self.last_error_at = finished_at
        self.last_scan_finished_at = finished_at
        self.last_scan_duration_seconds = duration
        self.current_scan_started_at = None
        self._append_recent_run("error", finished_at, duration, None, self.last_error)

    def mark_next_due(self, due_at: float | None) -> None:
        self.next_scan_due_at = _iso_utc(due_at)

    def snapshot(self) -> dict:
        return {
            "running": self.running,
            "current_scan_started_at": self.current_scan_started_at,
            "last_scan_started_at": self.last_scan_started_at,
            "last_scan_finished_at": self.last_scan_finished_at,
            "last_scan_duration_seconds": self.last_scan_duration_seconds,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
            "next_scan_due_at": self.next_scan_due_at,
            "scan_count": self.scan_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "last_result_summary": self.last_result_summary,
            "recent_runs": self.recent_runs[-10:],
        }

    def _append_recent_run(
        self,
        status: str,
        finished_at: str | None,
        duration: float | None,
        result_summary: dict | None,
        error: str | None,
    ) -> None:
        self.recent_runs.append(
            {
                "status": status,
                "started_at": self.last_scan_started_at,
                "finished_at": finished_at,
                "duration_seconds": duration,
                "result_summary": result_summary,
                "error": error,
            }
        )
        self.recent_runs = self.recent_runs[-10:]


def _parse_iso_utc(value: str | None) -> float | None:
    if value is None:
        return None
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict) -> None:
    body = json.dumps(payload, indent=2).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _html_response(handler: BaseHTTPRequestHandler, status: int, body: str) -> None:
    encoded = body.encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(encoded)))
    handler.end_headers()
    handler.wfile.write(encoded)


def _read_latest_signals(output_dir: Path) -> dict:
    path = output_dir / "latest_crypto_signals.json"
    if not path.exists():
        return {
            "raw_candidate_count": 0,
            "candidate_count": 0,
            "sendable_count": 0,
            "suppressed_count": 0,
            "filtered_count": 0,
            "market_context": None,
            "send_decisions": {},
            "market_filter_decisions": {},
            "candidates": [],
            "sendable": [],
            "suppressed": [],
            "filtered": [],
        }
    return json.loads(path.read_text(encoding="utf-8"))


def summary_payload(config: AppConfig, state: ScanState, signals: dict) -> dict:
    return {
        "health": health_payload(config, state),
        "signals": signals,
    }


def dashboard_html(health: dict, signals: dict) -> str:
    candidates = signals.get("candidates") or []
    cards = []
    for candidate in candidates[:20]:
        send_decision = candidate.get("send_decision") or {}
        filter_decision = candidate.get("market_filter_decision") or {}
        message = escape(str(candidate.get("message", "")))
        cards.append(
            "\n".join(
                [
                    "<article class=\"card\">",
                    f"<h2>{escape(str(candidate.get('symbol', 'unknown')))}</h2>",
                    f"<pre>{message}</pre>",
                    f"<p>Send: {escape(str(send_decision.get('reason', 'unknown')))}</p>",
                    f"<p>Filter: {escape(str(filter_decision.get('reason', 'not_evaluated')))}</p>",
                    "</article>",
                ]
            )
        )
    if not cards:
        cards.append("<article class=\"card\"><h2>Sinyal yok</h2><p>Son taramada aday üretilmedi.</p></article>")
    market = signals.get("market_context") or {}
    return f"""<!doctype html>
<html lang=\"tr\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
  <meta http-equiv=\"refresh\" content=\"60\">
  <title>crypto-anomaly-tracker</title>
  <style>
    body {{ margin: 0; background: #0f172a; color: #e2e8f0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }}
    main {{ max-width: 980px; margin: 0 auto; padding: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 12px; }}
    .card, .stat {{ border: 1px solid #334155; border-radius: 14px; background: #111827; padding: 16px; }}
    pre {{ white-space: pre-wrap; color: #f8fafc; font: 13px ui-monospace, SFMono-Regular, Menlo, monospace; }}
    a {{ color: #38bdf8; }}
  </style>
</head>
<body>
<main>
  <h1>crypto-anomaly-tracker</h1>
  <p>Hacimli hareketleri, piyasa filtresini ve Telegram gönderim kararlarını izler.</p>
  <section class=\"grid\">
    <div class=\"stat\"><strong>Service</strong><br>{escape(str(health.get("status", "unknown")))} / running={escape(str(health.get("running", False)))}</div>
    <div class=\"stat\"><strong>Signals</strong><br>{escape(str(signals.get("candidate_count", 0)))} kept, {escape(str(signals.get("filtered_count", 0)))} filtered</div>
    <div class=\"stat\"><strong>Market</strong><br>{escape(str(market.get("reference_symbol", "-")))} {escape(str(market.get("mode", "neutral")))}</div>
  </section>
  <h2>Son Sinyaller</h2>
  <section class=\"grid\">
    {"".join(cards)}
  </section>
  <p><a href=\"/summary\">/summary</a> · <a href=\"/signals\">/signals</a> · <a href=\"/health\">/health</a></p>
</main>
</body>
</html>"""


def handle_telegram_update(
    config: AppConfig,
    state: ScanState,
    update: dict,
    read_signals,
    send,
    start_scan,
) -> bool:
    message = update.get("message") or {}
    chat = message.get("chat") or {}
    chat_id = str(chat.get("id", ""))
    if not config.telegram_chat_id or chat_id != str(config.telegram_chat_id):
        return False
    text = message.get("text")
    if not isinstance(text, str):
        return False
    with state.lock:
        health = health_payload(config, state)
    response, action = command_response(text, health, read_signals(), config.public_base_url)
    if response is None:
        return False
    if action == "scan":
        start_scan()
    send(chat_id, response)
    return True


def _telegram_offset_path(config: AppConfig) -> Path:
    return config.output_dir / "telegram_updates_offset.json"


def _read_telegram_offset(config: AppConfig) -> int | None:
    path = _telegram_offset_path(config)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return int(payload["offset"])
    except Exception:
        return None


def _write_telegram_offset(config: AppConfig, offset: int) -> None:
    path = _telegram_offset_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"offset": offset}, indent=2), encoding="utf-8")


def _run_scan_locked(config: AppConfig, state: ScanState, send_telegram: bool) -> dict:
    with state.lock:
        if state.running:
            return {"status": "already_running"}
        state.record_start()
    try:
        result = run_scan(config, send_telegram=send_telegram)
        with state.lock:
            state.record_success(result)
        return result
    except Exception as exc:
        with state.lock:
            state.record_error(exc)
        raise


def _start_scan_thread(config: AppConfig, state: ScanState, send_telegram: bool) -> None:
    thread = threading.Thread(
        target=lambda: _run_scan_locked(config, state, send_telegram=send_telegram),
        daemon=True,
    )
    thread.start()


def start_telegram_command_polling(config: AppConfig, state: ScanState) -> threading.Thread | None:
    if not (config.telegram_commands_enabled and config.telegram_bot_token and config.telegram_chat_id):
        return None

    def loop() -> None:
        offset = _read_telegram_offset(config)
        while True:
            try:
                updates = get_updates(
                    config.telegram_bot_token or "",
                    offset=offset,
                    timeout_seconds=config.telegram_poll_timeout_seconds,
                )
                for update in updates:
                    update_id = int(update.get("update_id", 0))
                    offset = update_id + 1
                    _write_telegram_offset(config, offset)
                    handle_telegram_update(
                        config,
                        state,
                        update,
                        read_signals=lambda: _read_latest_signals(config.output_dir),
                        send=lambda chat_id, text: send_message(config.telegram_bot_token or "", chat_id, text),
                        start_scan=lambda: _start_scan_thread(config, state, send_telegram=True),
                    )
            except Exception as exc:
                with state.lock:
                    state.last_error = f"telegram command polling failed: {exc}"
                time.sleep(5)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


def make_handler(config: AppConfig, state: ScanState):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args) -> None:
            return

        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/health":
                with state.lock:
                    payload = health_payload(config, state)
                _json_response(self, 200, payload)
                return
            if parsed.path == "/signals":
                _json_response(self, 200, _read_latest_signals(config.output_dir))
                return
            if parsed.path == "/summary":
                signals = _read_latest_signals(config.output_dir)
                with state.lock:
                    payload = summary_payload(config, state, signals)
                _json_response(self, 200, payload)
                return
            if parsed.path == "/dashboard":
                signals = _read_latest_signals(config.output_dir)
                with state.lock:
                    health = health_payload(config, state)
                _html_response(self, 200, dashboard_html(health, signals))
                return
            _json_response(self, 200, {"service": "crypto-anomaly-tracker", "routes": ["/health", "/signals", "/summary", "/dashboard", "POST /scan"]})

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
            with state.lock:
                state.mark_next_due(time.time() + config.scan_interval_seconds)
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
    start_telegram_command_polling(active_config, state)
    server = ThreadingHTTPServer(("0.0.0.0", active_config.port), make_handler(active_config, state))
    server.serve_forever()
