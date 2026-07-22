# H-11 v4 G013 Formal-Aware Observer

## Scope

This Public-only observer improves the quality of a finite G013 candidate
monitor. It is not an actual-canary launcher and is not an authorization path.

For one completed M1 slot it runs the existing generation-bound preview. When
that preview is non-actionable, the operation ends after one Public M1 GET.
When it is actionable, the observer waits the frozen Public request gap and
performs one current-day H1 Public GET. The fresh H1 response is merged only in
memory with the official H1 history, excludes development and stage caches,
and proves that the completed H1 ATR(24) input is available.

## Invariants

- Maximum one H1 GET and only after an actionable M1 candidate.
- No same-slot retry. The existing preview slot marker remains authoritative.
- No candle-cache write, actual public-ledger mutation, actual-canary import or
  launch, Private API, Keychain access, notification service, permit, broker
  transport, order action, order sheet, or challenge.
- No direction, probability, price, raw candle, or identifier output. The
  report exposes only sanitized booleans, Public GET count, and broker POST
  count `0`.
- A formal-aware candidate plays one local macOS Glass sound once and stops the
  finite monitor. It does not promote to an actual-canary. The operator must
  start a new actual-canary, which independently obtains its fresh formal
  M1/H1 input and all activation gates.

## Failure behavior

An H1 failure, incomplete latest H1 bar, or invalid ATR input is terminal for
that slot and returns a fixed safe failure. It never falls back to another
source, reuses a previous H1 result, or performs another request.
