# H-11 v4 Unattended Public-only Shadow Adapter and Runner — No POST

Date: 2026-07-24

## Objective

Add the finite Public-only input adapter and bounded runner that feed the
already reviewed `v4_unattended_shadow_controller` (commit `e0c2b08`). This is
Phase 1 of the shadow track: it makes the controller observable against fresh
Public market data while remaining structurally incapable of any broker, Private
API, credential, notification, scheduler, or resident-process access.

This phase does not claim `live_ready`, `unattended_live_supported`,
`actual_post_authorized`, or performance proof.

## Components

- `backend/app/services/h11_v4_unattended_shadow_public_adapter.py` — the network
  layer the pure controller deliberately excludes. It lives in the `app.services`
  bridge (not `app.h11_auto`) because it composes the `app.h11_manual` model with
  the `app.h11_auto` controller, and those two packages must not import each other.
- `backend/scripts/h11_auto_v4_unattended_shadow_run.py` — a bounded, finite
  runner (max cycles / fixed interval; not a resident process).
- `backend/app/tests/h11_auto/test_v4_unattended_shadow_public_adapter_no_post.py`
  — fake `httpx` transport, recorded Public fixtures, cross-check, and isolation
  tests.

## Frozen reuse

- Direction: the frozen SHORT_V1 / 30-minute inference over the exact 31 completed
  M1 bars ending at the completed slot, via the shared `predict_short_model` /
  `map_probability` / `extract_formal_signal_from_sanitized_current` primitives.
- Risk width: ATR(24) as the mean true range of the latest 24 completed **official
  H1** bars only.
- The controller's frozen contract (`SHORT_V1`, 30m, `USD_JPY`, 1,000, `MARKET`,
  one entry per JST day, config hash `sha256:ca08df18…`) is unchanged.

### Fidelity guarantee and its bound

`test_signal_and_atr_match_the_frozen_actual_canary_builder` feeds identical
frames to both the adapter and the actual-canary `build_g013_formal_canary_input`
and asserts the identical BUY/SELL `FormalSignal` fingerprint and ATR, plus a
direct `_completed_h1_atr_24` equality against the canonical helper. This pins the
post-inference plumbing and the ATR arithmetic. It does **not** drive the two
data-assembly paths from the same raw klines, and the adapter currently
**replicates** (rather than imports) the ATR / completed-bar / snapshot helpers,
because the isolation guard forbids the adapter importing the `*canary*` module.
The single-source refactor (hoisting the pure inference/ATR/window helpers into a
neutrally-named shared module imported by both) is deliberately deferred: it would
edit actual-canary code, which is out of scope for this phase and requires a new
reviewed generation. Until then, cross-path fidelity is pinned by the tests above
plus the ATR-helper equality, and any divergence in the shared arithmetic fails a
test rather than passing silently.

## Public fetch boundary

Per completed M1 slot the adapter performs exactly five Public GETs through the
existing `GmoPublicMarketDataClient`: `/public/v1/status`, `/public/v1/ticker`,
`/public/v1/klines` for today's M1, and H1 for the previous and current JST day.
The same completed slot is claimed once via an `O_EXCL` marker under
`backend/shadow_exports/`; a claimed slot is never retried. Any network, schema,
freshness, or history failure is fail-closed with a fixed safe label.

## Why a Public-only cycle always blocks safely

Account flat, active-order count, boot reconciliation, and a fresh broker
snapshot cannot be observed without a Private GET. The adapter therefore reports
these preflight dimensions fail-closed (`boot_reconciled=False`,
`broker_snapshot_fresh=False`, `notification_path_ready=False`), so every
Public-only cycle resolves to `SHADOW_BLOCKED_SAFE` — never
`SHADOW_WOULD_ENTER_NON_AUTHORIZING`. Public-derived account/order counts are not
treated as an authoritative flat claim. The observable value of this phase is:
the signal / market / quote / spread gates are exercised against live Public data
while the broker gates remain honestly unobserved.

Known limitations (all fail-closed — a limitation means "no observation," never a
wrong value):

- Because a Public-only cycle never becomes actionable, the controller's
  daily-entry-cap path is not exercised by a live Public run. It stays covered by
  the controller unit tests and is reserved for the full-operational (Private GET)
  phase.
- The adapter assembles H1 history from only the previous and current JST day (no
  local cache). Around 00:00–01:00 JST, just after JST midnight, and in the first
  hour of the FX trading week it may not yet have 25 completed H1 (or 31 completed
  M1) bars, and returns `SHADOW_PUBLIC_*_HISTORY_INSUFFICIENT`. This is expected
  blindness, not a fault; an operator should not read "no observation" as an error.

## Running the shadow

From the repository root (paths resolve against the module, so the default
`--shadow-root` and confinement work regardless of cwd):

```
python -m scripts.h11_auto_v4_unattended_shadow_run --max-cycles 30 --interval-seconds 60
```

- `--max-cycles` (1–240) and `--interval-seconds` (0–3600) bound the run; the
  process exits when the budget is spent. It is not a resident process.
- Each cycle prints one sanitized JSON line: `{"cycle": N, "status": ...,
  "blocked_reasons": [...], "broker_post_authorized": false, ...}`. A healthy
  Public cycle prints `SHADOW_BLOCKED_SAFE` with the broker/account/notification
  reasons only (the signal/market/quote/spread gates passed). Failures print a
  fixed safe label (`SHADOW_PUBLIC_*` / a controller label) with `recorded=false`.
- Exit code `0` = the run completed; `2` = a startup failure (invalid model file,
  store init). Never a stack trace.
- Do not set `--interval-seconds 0` against live data: successive cycles land on
  the same completed minute slot and are refused (`SHADOW_PUBLIC_SLOT_ALREADY_OBSERVED`),
  wasting the cycle budget. Use an interval near the 60-second slot cadence.
- State (SQLite ledger, per-slot `O_EXCL` markers, lock) lives only under the
  gitignored `backend/shadow_exports/`; nothing is ever committed. Slot markers
  accumulate one file per observed minute; delete the run directory to reset a
  finished observation window (the sticky-HALT contract means the ledger has no
  in-process reset).

## Structural exclusions

The adapter and runner have no import, reference, or call to:

- Private API, Keychain, or credential access
- actual transport / adapter / coordinator, hard guard, or activation permit
- broker order, cancel, close, or OCO write endpoints
- Pushover or SMTP
- scheduler, background loop, LaunchAgent, launchd, cron, or resident process
- any environment / `.env` / `LIVE=true` live-enable bridge

`test_adapter_reachable_app_modules_are_public_only` walks the adapter's static
import graph and rejects any reachable `app.*` module whose name contains an
actual / coordinator / private / hard_guard / canary / launchd / permit /
notification / settlement / broker fragment. The only external dependency is the
Public `httpx` client.

## Promotion sequence

1. (This phase) Public-only finite adapter + bounded runner, structurally no-POST.
2. Run a bounded Public shadow and audit ledger, duplicate refusal, stale
   rejection, HALT, and restart recovery.
3. Separately reviewed full-operational shadow adding sanitized Private GET
   preflight and a notification lane under a new generation.
4. Freeze machine-checkable shadow→live promotion criteria.
5. Separately reviewed unattended live adapter for a fixed small size; live
   promotion cannot be an environment toggle and cannot reuse a shadow
   observation as broker authorization.

The G013 canary and post-canary generations remain closed and are not promotion
artifacts for this adapter.
