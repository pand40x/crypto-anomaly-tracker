#!/usr/bin/env bash
set -euo pipefail

account="${KEYCHAIN_ACCOUNT:-finance-anomaly-tracker}"
output="${1:-.env}"

get_secret() {
  local service="$1"
  security find-generic-password -s "$service" -a "$account" -w
}

telegram_token="$(get_secret TELEGRAM_BOT_TOKEN)"
telegram_user_id="$(get_secret TELEGRAM_USER_ID)"

cat > "$output" <<EOF
PORT=8080
PUBLISHED_PORT=18080
ANOMALY_SYMBOL_LIMIT=150
ANOMALY_GLOBAL_LIMIT=10
ANOMALY_INTERVAL=4h
ANOMALY_LOOKBACK_DAYS=730
ANOMALY_ROLLING_BARS=42
ANOMALY_MIN_ABS_PCT_CHANGE=1.0
ANOMALY_MIN_VOLUME_RATIO=1.5
ANOMALY_SCAN_INTERVAL_SECONDS=14400
ANOMALY_SCAN_WORKERS=8
ANOMALY_COOLDOWN_SECONDS=43200
ANOMALY_RUN_ON_START=true
TELEGRAM_BOT_TOKEN=${telegram_token}
TELEGRAM_USER_ID=${telegram_user_id}
EOF

chmod 600 "$output"
echo "Wrote $output"
