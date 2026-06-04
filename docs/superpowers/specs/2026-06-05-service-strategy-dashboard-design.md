# Service, Strategy, and Dashboard Design

## Goal

Finish the remaining product slices after the Telegram quality release: make the live service observable, reduce weak false-positive alerts with a BTC market-regime filter, and add a dependency-free dashboard/API foundation.

## Scope

- Add scan lifecycle metadata to `/health`: running state, start/finish times, duration, success/failure counts, last result summary, and next scheduled run.
- Persist market-filter metadata in `/signals`: market context, filtered candidates, and filter decisions.
- Use BTCUSDT as a configurable market reference. In risk-off conditions, suppress weak bullish signals; in risk-on conditions, suppress weak bearish signals. Critical signals still pass.
- Add `GET /summary` for combined health + signal data.
- Add `GET /dashboard` for a simple HTML status page that renders recent signals and send/filter decisions.

Out of scope:

- Database storage.
- Frontend build tooling.
- External alert providers.
- LLM explanations.

## Architecture

`service.py` owns HTTP presentation and in-memory scan lifecycle state. `ScanState` records scan starts, successes, failures, recent run summaries, and scheduler due times.

`runtime.py` owns environment configuration for the market filter. Defaults keep the filter enabled with BTCUSDT as the reference symbol.

`scoring.py` owns pure market-regime decision logic. It returns data-only decisions so `runner.py` can persist them and continue owning scan orchestration.

`runner.py` computes raw candidates, applies the market filter, re-ranks kept candidates, computes cooldown decisions, persists the result, and sends Telegram messages only for kept/sendable candidates.

## Behavior

- `/health` remains safe: it never exposes tokens or raw env values.
- `/signals` remains backward compatible for existing fields and adds:
  - `raw_candidate_count`
  - `filtered_count`
  - `filtered`
  - `market_context`
  - `market_filter_decisions`
- `/summary` returns `{ "health": ..., "signals": ... }`.
- `/dashboard` returns HTML using only standard library rendering.
- Market filter is transparent: filtered candidates are visible in JSON with a reason.

## Verification

- Add red/green unit tests for scan lifecycle metadata.
- Add red/green unit tests for market-regime filtering.
- Add red/green unit tests for summary/dashboard rendering.
- Run the full unit test suite.
- Push and deploy to Dokploy.
- Verify live `/health`, `/signals`, `/summary`, and `/dashboard`.

