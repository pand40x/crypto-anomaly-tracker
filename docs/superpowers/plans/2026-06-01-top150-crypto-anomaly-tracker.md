# Top150 Crypto Anomaly Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a testable crypto anomaly engine that calibrates per-asset thresholds, ranks Top150 USDT spot assets globally, and emits human-readable signal candidates.

**Architecture:** Keep the core scorer pure and dependency-free. Binance fetching, Top150 universe selection, report generation, and later Telegram delivery sit outside the scoring module.

**Tech Stack:** Python 3 stdlib, `unittest`, Binance public REST API, JSON/CSV/Markdown outputs.

---

### File Structure

- Create `anomaly_tracker/models.py`: dataclasses for candles, scored rows, thresholds, and signal candidates.
- Create `anomaly_tracker/scoring.py`: rolling robust z-score, per-asset score, percentile thresholds, and signal candidate selection.
- Create `anomaly_tracker/universe.py`: Binance USDT spot Top150 selector with stablecoin/leveraged-token filters.
- Create `anomaly_tracker/binance.py`: dependency-free Binance REST client for klines, tickers, and exchange info.
- Create `anomaly_tracker/humanize.py`: non-technical Turkish reason text for Telegram-ready messages.
- Create `anomaly_tracker/cli.py`: command line entry point for `scan` and `report`.
- Create `tests/test_scoring.py`: deterministic scoring tests with synthetic candles.
- Create `tests/test_universe.py`: Top150 filtering/ranking tests with fixture-like dictionaries.

### Task 1: Scoring Contract

- [ ] Write failing tests for robust z-score behavior, per-asset threshold percentiles, and global ranking.
- [ ] Run `rtk python3 -m unittest tests.test_scoring -v` and confirm the package import fails or behavior is missing.
- [ ] Implement `models.py`, `scoring.py`, and `humanize.py` minimally.
- [ ] Run `rtk python3 -m unittest tests.test_scoring -v` and confirm all tests pass.

### Task 2: Binance Top150 Universe

- [ ] Write failing tests for excluding stablecoins, leveraged tokens, inactive symbols, and sorting by quote volume.
- [ ] Run `rtk python3 -m unittest tests.test_universe -v` and confirm behavior is missing.
- [ ] Implement `universe.py` and `binance.py`.
- [ ] Run `rtk python3 -m unittest tests.test_universe -v` and confirm all tests pass.

### Task 3: CLI Output

- [ ] Add `scan` CLI that can run with explicit symbols or Binance Top150.
- [ ] Emit JSON and Markdown summaries under `outputs/`.
- [ ] Smoke test with `BTCUSDT,ETHUSDT` and a short lookback.
- [ ] Keep Telegram delivery out of scope until signal quality is reviewed.

### Acceptance Checks

- Per-asset thresholds exist for every scanned symbol.
- Telegram candidate signals require both asset-specific threshold pass and global rank pass.
- Output includes human-readable Turkish explanation without claiming external news causality.
- Tests pass with stdlib only.
