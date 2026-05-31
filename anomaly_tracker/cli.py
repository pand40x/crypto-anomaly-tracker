from __future__ import annotations

import argparse
import os

from anomaly_tracker.runner import run_scan
from anomaly_tracker.runtime import AppConfig
from anomaly_tracker.service import serve


INTERVALS = ("1h", "4h", "1d")


def _parse_symbols(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip().upper() for item in value.split(",") if item.strip()]


def scan(args: argparse.Namespace) -> int:
    env = dict(os.environ)
    env.update({
        "ANOMALY_SYMBOL_LIMIT": str(args.limit),
        "ANOMALY_GLOBAL_LIMIT": str(args.global_limit),
        "ANOMALY_INTERVAL": args.interval,
        "ANOMALY_LOOKBACK_DAYS": str(args.lookback_days),
        "ANOMALY_ROLLING_BARS": str(args.rolling_bars),
        "ANOMALY_MIN_ABS_PCT_CHANGE": str(args.min_abs_pct_change),
        "ANOMALY_MIN_VOLUME_RATIO": str(args.min_volume_ratio),
        "ANOMALY_OUTPUT_DIR": args.output_dir,
    })
    config = AppConfig.from_env(env)
    result = run_scan(
        config,
        send_telegram=args.send_telegram,
        symbols=_parse_symbols(args.symbols),
    )
    print(f"signals={result['candidate_count']} sendable={result['sendable_count']} output={args.output_dir}")
    return 0


def serve_command(args: argparse.Namespace) -> int:
    serve(AppConfig.from_env())
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="anomaly-tracker")
    subparsers = parser.add_subparsers(dest="command", required=True)

    scan_parser = subparsers.add_parser("scan", help="scan crypto symbols for latest anomaly candidates")
    scan_parser.add_argument("--symbols", help="comma separated symbols, e.g. BTCUSDT,ETHUSDT")
    scan_parser.add_argument("--limit", type=int, default=150, help="Top USDT spot symbols by 24h quote volume")
    scan_parser.add_argument("--global-limit", type=int, default=10, help="max Telegram candidates per scan")
    scan_parser.add_argument("--interval", choices=INTERVALS, default="4h")
    scan_parser.add_argument("--lookback-days", type=int, default=730)
    scan_parser.add_argument("--rolling-bars", type=int, default=42)
    scan_parser.add_argument("--min-abs-pct-change", type=float, default=1.0)
    scan_parser.add_argument("--min-volume-ratio", type=float, default=1.5)
    scan_parser.add_argument("--output-dir", default="outputs")
    scan_parser.add_argument("--send-telegram", action="store_true")
    scan_parser.set_defaults(func=scan)

    serve_parser = subparsers.add_parser("serve", help="run HTTP service and background scheduler")
    serve_parser.set_defaults(func=serve_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
