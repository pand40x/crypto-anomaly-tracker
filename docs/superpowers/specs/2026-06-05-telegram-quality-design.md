# Telegram Quality Design

## Goal

Improve the Telegram alert experience for `crypto-anomaly-tracker` without changing the core anomaly scoring model. The first slice should make every alert easier to read, easier to triage, and easier to audit through the JSON API.

## Scope

- Format Telegram messages as a compact multi-line card.
- Add clear Turkish labels for importance, direction, rank, source interval, volume, and score.
- Keep the existing Binance scan and scoring algorithm unchanged.
- Expose send decisions in the persisted scan payload so `/signals` can show which candidates were sent and which were suppressed by cooldown.
- Keep Telegram sending best-effort and dependency-free.

Out of scope for this slice:

- New frontend dashboard.
- Database storage.
- New market data providers.
- Machine-learning or LLM explanations.

## Architecture

`outputs.py` remains responsible for presentation-only formatting. It will expose small formatting helpers and `candidate_to_message(candidate)` will return the new multi-line Telegram card.

`state.py` remains responsible for cooldown rules. It will add a decision method that returns both `send` and a reason, while preserving the existing `should_send()` API for compatibility.

`runner.py` remains the orchestration layer. It will ask `CooldownState` for a send decision per candidate, send only candidates marked sendable, and persist both `sendable` and `suppressed` lists.

## Behavior

A typical Telegram message should look like:

```text
HOME | $0.0506 | 4s +36.89%
Onem: kritik | Yon: alim | Sira: #1 | Skor: 6.20
Sebep: hacimli alim, genis mum
Hacim: $13.8M
```

Fast-lane candidates append `| FAST` on the first line to preserve the existing distinction.

Cooldown decisions:

- First signal for a symbol is sendable.
- A repeated signal inside cooldown is suppressed unless its score is at least 15% stronger than the last sent score.
- Suppressed candidates remain in `candidates` and are also written to a new `suppressed` list with `send_decision` metadata.

## Testing

- Unit-test the new Telegram message format with a `HOMEUSDT` example matching production-style alerts.
- Unit-test fast-lane label preservation.
- Unit-test cooldown decision metadata for first send, suppressed repeat, and stronger repeat.
- Unit-test persisted scan payload includes `sendable`, `suppressed`, and `send_decisions`.
- Run the full unittest suite before committing.

