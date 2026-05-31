# Crypto Anomaly Tracker

Dependency-free Python service for Binance crypto anomaly scans and Telegram alerts.

## Local Commands

Run tests:

```bash
rtk python3 -m unittest discover -s tests -v
```

Run a manual BTC/ETH scan:

```bash
rtk python3 -m anomaly_tracker.cli scan --symbols BTCUSDT,ETHUSDT --lookback-days 90 --rolling-bars 24 --output-dir outputs/smoke
```

Create a local `.env` from macOS Keychain:

```bash
rtk proxy scripts/write_local_env_from_keychain.sh .env
```

Run the HTTP service:

```bash
rtk python3 -m anomaly_tracker.cli serve
```

Routes:

- `GET /health`
- `GET /signals`
- `POST /scan`
- `POST /scan?send=1`

## Algorithm

The scanner calibrates thresholds per asset, then ranks the latest closed candle globally:

- price shock against the asset's recent normal behavior
- quote volume expansion
- candle range expansion
- 7-day band breakout

Telegram candidates must pass their own asset-specific signal threshold and the global rank limit. Cooldown suppresses repeated messages for the same symbol unless the new score is at least 15% stronger.

## Dokploy

The included `docker-compose.yml` uses `env_file: .env` because Dokploy writes compose variables into a `.env` file beside the compose file. The service listens on `PORT`, defaults to `8080`, and stores state in the named Docker volume.

Deploy with an existing Compose service:

```bash
DOKPLOY_URL=https://your-dokploy.example \
DOKPLOY_COMPOSE_ID=your-compose-id \
rtk python3 scripts/dokploy_deploy.py
```

Create a new Compose service in an existing Dokploy environment:

```bash
DOKPLOY_URL=https://your-dokploy.example \
DOKPLOY_ENVIRONMENT_ID=your-environment-id \
rtk python3 scripts/dokploy_deploy.py
```
