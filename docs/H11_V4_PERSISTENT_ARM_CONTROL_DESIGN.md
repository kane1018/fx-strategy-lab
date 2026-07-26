# H-11 v4 Persistent Arm Control V1

Status: `IMPLEMENTED_NO_POST_VALIDATION_IN_PROGRESS`

## Goal

The localhost manual signal UI exposes only `ON` and `OFF` for the unattended
controller. The UI never imports broker-write code and only changes a
generation-bound local arm artifact.

## Safety contract

- Missing, malformed, symlinked, stale-generation, or stale-reviewed-digest
  state is `DISARMED`.
- `ON` requires a clean reviewed generation whose frozen contract explicitly
  sets both `live_ready=true` and `unattended_live_supported=true`.
- The scheduler checks arm state before Public signal preparation, Keychain
  construction, Private API, notifications, permit issuance, or broker write.
- `OFF` blocks future entries. It does not cancel OCO, close a position, clear
  HALT, reset risk, or delete no-retry markers.
- The manual UI Private GET client is disabled while the current generation is
  armed.
- The daily authorization is not used by the new path. Persistent arm plus all
  fresh runtime gates mint only one-use generation/cycle proofs.
- The existing coordinator SQLite `MARKET_ENTRY` rows are the immutable attempt
  authority. Their JST-day count must exactly equal `risk.json.entries_today`
  before and after each reservation; mismatch latches HALT.
- The final arm check and the entry-reserved notification run after attempt and
  risk persistence but before the MARKET transport call.
- `OFF` while a protected position exists projects `EXIT_ONLY`: no new MARKET
  entry, while cancel/OCO/position-specific exit and monitoring remain enabled.
- If OFF or notification failure is detected in the narrow post-persistence,
  pre-transport window, no broker write occurs and the generation latches HALT.

## Canonical state

The arm artifact is stored outside the repository under the canonical
`~/Library/Application Support/fx-strategy-lab-h11-v4-unattended-live` root.
It binds:

- exact generation digest;
- exact reviewed-files digest;
- `ARMED` or `DISARMED`;
- monotonically increasing revision;
- timezone-aware change timestamp;
- fixed local UI source label.

No credential, account value, direction, quote, raw response, or broker ID is
stored.

## Current activation boundary

This control-plane implementation does not authorize a broker POST. The
current frozen generation remains `actual_post_authorized=false`,
`live_ready=false`, and `unattended_live_supported=false`; therefore its ON
operation is refused.

## Sequential-entry authority

- Maximum: 30 MARKET attempts per JST trading day.
- This is not 30 simultaneous positions. A new cycle can be reserved only after
  every prior cycle is authoritatively flat-reconciled.
- Daily/monthly loss, consecutive-loss, dead-man, heartbeat continuity,
  market/signal/account gates, persistent HALT, and operator OFF can stop entry
  before 30.
- An attempt is consumed before transport. Unknown or failed boundary outcomes
  are never retried as the same action.
