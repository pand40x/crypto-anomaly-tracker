# Telegram Quality Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make Telegram anomaly alerts easier to read and expose send/suppress decisions in the JSON scan output.

**Architecture:** Keep scoring unchanged. Presentation changes live in `anomaly_tracker/outputs.py`, cooldown decisions live in `anomaly_tracker/state.py`, and scan orchestration/persistence updates live in `anomaly_tracker/runner.py`.

**Tech Stack:** Python standard library, `unittest`, dependency-free HTTP service.

---

### Task 1: Telegram Message Card

**Files:**
- Modify: `tests/test_outputs.py`
- Modify: `anomaly_tracker/outputs.py`

- [x] **Step 1: Write failing tests**

Add tests that expect a multi-line message for `HOMEUSDT`, including importance, direction, rank, score, reason, and compact volume. Add a second test that a fast-lane candidate keeps `| FAST` on the first line.

- [x] **Step 2: Verify red**

Run: `rtk python3 -m unittest tests.test_outputs -v`

Observed: failures showed the current one-line message did not include the new lines.

- [x] **Step 3: Implement minimal formatter**

Updated `candidate_to_message()` and added small helpers for Turkish labels. Scoring is unchanged.

- [x] **Step 4: Verify green**

Run: `rtk python3 -m unittest tests.test_outputs -v`

Observed: all output tests passed.

### Task 2: Cooldown Decision Metadata

**Files:**
- Modify: `tests/test_runtime.py`
- Modify: `anomaly_tracker/state.py`

- [x] **Step 1: Write failing tests**

Added tests for `CooldownState.send_decision(candidate)` returning `first_signal`, `cooldown`, and `stronger_signal` decisions.

- [x] **Step 2: Verify red**

Run: `rtk python3 -m unittest tests.test_runtime -v`

Observed: failure because `send_decision` did not exist.

- [x] **Step 3: Implement minimal decision method**

Added `send_decision()` while keeping `should_send()` as a compatibility wrapper.

- [x] **Step 4: Verify green**

Run: `rtk python3 -m unittest tests.test_runtime -v`

Observed: all runtime tests passed.

### Task 3: Persist Send/Suppress Decisions

**Files:**
- Modify: `tests/test_runner.py`
- Modify: `anomaly_tracker/runner.py`

- [x] **Step 1: Write failing tests**

Updated `persist_scan_result()` tests to pass a `send_decisions` mapping and expect `suppressed`, `suppressed_count`, and per-candidate `send_decision` fields in `latest_crypto_signals.json`.

- [x] **Step 2: Verify red**

Run: `rtk python3 -m unittest tests.test_runner -v`

Observed: failure because `candidate_decision_key` and decision persistence did not exist yet.

- [x] **Step 3: Implement persistence and runner wiring**

Calculated decisions once in `run_scan()`, sent only sendable candidates, recorded sent candidates, and persisted decision metadata.

- [x] **Step 4: Verify green**

Run: `rtk python3 -m unittest tests.test_runner -v`

Observed: runner tests passed.

### Task 4: Full Verification and Commit

**Files:**
- Verify all changed files.

- [x] **Step 1: Run full suite**

Run: `rtk python3 -m unittest discover -s tests -v`

Observed: 17 tests passed.

- [x] **Step 2: Inspect git diff**

Run: `rtk git diff --stat` and `rtk git diff`

- Observed: only docs, output formatting, cooldown decision metadata, runner persistence, and tests changed.

- [ ] **Step 3: Commit**

Run: `rtk git add ...` and `rtk git commit -m "feat: improve telegram alert quality"`

### Task 5: Deployment Readiness

**Files:**
- No code changes expected.

- [ ] **Step 1: Confirm remote state**

Run: `rtk git status --short --branch`

- [ ] **Step 2: Push for Dokploy auto-deploy**

Run: `rtk git push`
