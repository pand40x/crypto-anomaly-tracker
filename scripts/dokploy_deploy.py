#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def keychain(service: str, account: str = "finance-anomaly-tracker") -> str:
    return subprocess.check_output(
        ["security", "find-generic-password", "-s", service, "-a", account, "-w"],
        text=True,
    ).strip()


def required_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(f"Missing {name}")
    return value.rstrip("/") if name == "DOKPLOY_URL" else value


def api(base_url: str, token: str, method: str, path: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{base_url}/api/{path}",
        data=data,
        headers={"Content-Type": "application/json", "x-api-key": token},
        method=method,
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read().decode("utf-8")
        return json.loads(raw) if raw else {}


def env_text() -> str:
    telegram_token = os.environ.get("TELEGRAM_BOT_TOKEN") or keychain("TELEGRAM_BOT_TOKEN")
    telegram_user_id = os.environ.get("TELEGRAM_USER_ID") or keychain("TELEGRAM_USER_ID")
    return "\n".join(
        [
            "PORT=8080",
            f"ANOMALY_SYMBOL_LIMIT={os.environ.get('ANOMALY_SYMBOL_LIMIT', '150')}",
            f"ANOMALY_GLOBAL_LIMIT={os.environ.get('ANOMALY_GLOBAL_LIMIT', '10')}",
            f"ANOMALY_INTERVAL={os.environ.get('ANOMALY_INTERVAL', '4h')}",
            f"ANOMALY_LOOKBACK_DAYS={os.environ.get('ANOMALY_LOOKBACK_DAYS', '730')}",
            f"ANOMALY_ROLLING_BARS={os.environ.get('ANOMALY_ROLLING_BARS', '42')}",
            f"ANOMALY_MIN_ABS_PCT_CHANGE={os.environ.get('ANOMALY_MIN_ABS_PCT_CHANGE', '1.0')}",
            f"ANOMALY_MIN_VOLUME_RATIO={os.environ.get('ANOMALY_MIN_VOLUME_RATIO', '1.5')}",
            f"ANOMALY_SCAN_INTERVAL_SECONDS={os.environ.get('ANOMALY_SCAN_INTERVAL_SECONDS', '14400')}",
            f"ANOMALY_COOLDOWN_SECONDS={os.environ.get('ANOMALY_COOLDOWN_SECONDS', '43200')}",
            f"ANOMALY_RUN_ON_START={os.environ.get('ANOMALY_RUN_ON_START', 'true')}",
            f"TELEGRAM_BOT_TOKEN={telegram_token}",
            f"TELEGRAM_USER_ID={telegram_user_id}",
        ]
    )


def main() -> int:
    base_url = required_env("DOKPLOY_URL")
    token = os.environ.get("DOKPLOY_API_TOKEN") or keychain("DOKPLOY_API_TOKEN")
    compose_file = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    compose_id = os.environ.get("DOKPLOY_COMPOSE_ID")
    environment_id = os.environ.get("DOKPLOY_ENVIRONMENT_ID")

    if compose_id:
        print("Updating existing Dokploy compose")
        api(
            base_url,
            token,
            "POST",
            "compose.update",
            {
                "composeId": compose_id,
                "name": "finance-anomaly-tracker",
                "appName": "finance-anomaly-tracker",
                "composeFile": compose_file,
                "env": env_text(),
                "sourceType": "raw",
                "composeType": "docker-compose",
            },
        )
    else:
        if not environment_id:
            raise SystemExit("Set DOKPLOY_COMPOSE_ID for update or DOKPLOY_ENVIRONMENT_ID for create")
        print("Creating Dokploy compose")
        created = api(
            base_url,
            token,
            "POST",
            "compose.create",
            {
                "name": "finance-anomaly-tracker",
                "description": "Crypto anomaly tracker with Telegram alerts",
                "environmentId": environment_id,
                "appName": "finance-anomaly-tracker",
                "composeFile": compose_file,
                "composeType": "docker-compose",
            },
        )
        compose_id = created.get("composeId") or created.get("id")
        if not compose_id:
            print(json.dumps(created, indent=2))
            raise SystemExit("Dokploy did not return compose id")
        api(base_url, token, "POST", "compose.update", {"composeId": compose_id, "env": env_text()})

    print("Deploying Dokploy compose")
    api(base_url, token, "POST", "compose.deploy", {"composeId": compose_id})
    print(f"Deployed composeId={compose_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
