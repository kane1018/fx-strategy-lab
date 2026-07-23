# H-11 v4 Unattended Shadow Controller — No POST

Date: 2026-07-23

## Objective

Build the decision core that can later be shared by a limited unattended live
generation, while keeping this phase structurally incapable of broker access.
The controller consumes one caller-supplied formal signal and one sanitized
snapshot, evaluates every frozen entry gate, and records a non-authorizing
shadow decision.

This phase does not claim `live_ready`, `unattended_live_supported`, or
performance proof.

## Frozen scope

- strategy: `SHORT_V1`
- horizon: `30m`
- symbol: `USD_JPY`
- size: 1,000 units
- execution type: `MARKET`
- maximum entries per JST day: 1
- maximum formal signal age: 120 seconds
- maximum quote age: 5 seconds
- maximum spread: 2.0 pips
- maximum reference deviation: 5.0 pips
- maximum planned loss: existing v4 per-trade bound

Direction comes only from the formal `BUY` or `SELL` signal. The controller
cannot infer or override direction, size, symbol, execution type, protection
contract, or risk limits.

## Shared controller boundary

The controller evaluates:

- signal identity, finality, age, expiry, and frozen policy match
- frozen entry-time window
- market OPEN and fresh quote
- spread and reference deviation
- account flat and zero active orders
- process lock, clock, notification readiness, fresh broker snapshot
- daily, monthly, consecutive-loss, and operator HALT state
- planned loss against the frozen per-trade cap

An actionable result is represented only as
`SHADOW_WOULD_ENTER_NON_AUTHORIZING`. Its intent type fixes
`broker_post_authorized=false` and `actual_post_count=0`; it is not a permit,
hard-guard input, transport authorization, or live generation artifact.

## Durable shadow rules

The SQLite shadow ledger is stored only under ignored
`backend/shadow_exports/` during operation. It binds one controller digest,
uses a unique formal-signal fingerprint and cycle reference, serializes writes
with `BEGIN IMMEDIATE`, rejects duplicate signals, and changes a second
actionable signal on the same JST day to a safe blocked result.

The ledger constructor rejects every path outside the repository's ignored
`backend/shadow_exports/` root. Controller-digest validation, sticky-HALT
evaluation, duplicate detection, the JST daily cap, and decision insertion
occur under the same write transaction. A sticky HALT may be latched but this
API has no clear or reset method. Process-lock contention returns a sanitized
non-recorded blocked report.

## Structural exclusions

The module has no import or reference to:

- Private API or Keychain
- actual transport, actual adapter, actual coordinator, or hard guard
- broker order, cancel, close, or OCO write endpoints
- activation permits or operator confirmation
- Public network retrieval
- Pushover or SMTP
- scheduler, polling loop, LaunchAgent, cron, or resident process

## Promotion sequence

1. Validate the pure controller and persistence with fake inputs.
2. Add a finite Public-only shadow input adapter and sanitized notification
   output without changing the controller.
3. Run bounded shadow observation and audit duplicate/day/risk/HALT behavior.
4. Independently review and freeze a new unattended generation.
5. Add a separately reviewed live adapter for fixed small size. Live promotion
   cannot be an environment toggle and cannot reuse a shadow intent as broker
   authorization.

The current G013 canary and post-canary generations remain closed and are not
promotion artifacts for this controller.
