# Service Strategy Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the remaining product slices: observability, BTC market-regime filtering, and a mini dashboard/API foundation.

**Architecture:** Keep the app dependency-free. Add pure decision helpers in `scoring.py`, orchestration metadata in `runner.py`, lifecycle state and HTML/API presentation in `service.py`, and config defaults in `runtime.py`.

**Tech Stack:** Python standard library, `unittest`, Dokploy compose deploy.

---

### Task 1: Live Service Observability

**Files:**
- Modify: `tests/test_service.py`
- Modify: `anomaly_tracker/service.py`

- [x] **Step 1: Write failing tests**

Test `ScanState` records start/success/failure metadata and `health_payload(config, state)` exposes safe operational fields.

- [x] **Step 2: Run red test**

Run: `rtk python3 -m unittest tests.test_service -v`

- [x] **Step 3: Implement lifecycle metadata**

Add `ScanState.record_start`, `record_success`, `record_error`, `mark_next_due`, and include those fields in health output.

- [x] **Step 4: Run green test**

Run: `rtk python3 -m unittest tests.test_service -v`

### Task 2: Market-Regime Strategy Filter

**Files:**
- Modify: `tests/test_scoring.py`
- Modify: `tests/test_runtime.py`
- Modify: `tests/test_runner.py`
- Modify: `anomaly_tracker/models.py`
- Modify: `anomaly_tracker/runtime.py`
- Modify: `anomaly_tracker/scoring.py`
- Modify: `anomaly_tracker/runner.py`

- [x] **Step 1: Write failing tests**

Test BTC risk-off suppresses weak bullish signals, keeps critical bullish signals, and persists filtered candidate metadata.

- [x] **Step 2: Run red tests**

Run: `rtk python3 -m unittest tests.test_scoring tests.test_runtime tests.test_runner -v`

- [x] **Step 3: Implement filter**

Add config, pure decision helpers, and runner persistence.

- [x] **Step 4: Run green tests**

Run: `rtk python3 -m unittest tests.test_scoring tests.test_runtime tests.test_runner -v`

### Task 3: Summary API and Mini Dashboard

**Files:**
- Modify: `tests/test_service.py`
- Modify: `anomaly_tracker/service.py`

- [x] **Step 1: Write failing tests**

Test `summary_payload` and `dashboard_html` produce safe JSON/HTML with latest signal data.

- [x] **Step 2: Run red test**

Run: `rtk python3 -m unittest tests.test_service -v`

- [x] **Step 3: Implement routes**

Add `GET /summary` and `GET /dashboard` while keeping root route usable.

- [x] **Step 4: Run green test**

Run: `rtk python3 -m unittest tests.test_service -v`

### Task 4: Full Verification, Commit, Deploy

- [x] **Step 1: Run full suite**

Run: `rtk python3 -m unittest discover -s tests -v`

Observed: 27 tests passed.

- [ ] **Step 2: Commit and push**

Run: `rtk git add ...`, `rtk git commit -m "feat: add observability strategy filter and dashboard"`, and `rtk git push`.

- [ ] **Step 3: Deploy and verify**

Call Dokploy `compose.deploy`, then verify live `/health`, `/signals`, `/summary`, and `/dashboard`.
