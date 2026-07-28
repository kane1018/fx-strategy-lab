# H-11 v4 G020 Public-only shadow commissioning design

## Scope

G020 is a corrective no-POST generation produced after the G019 design-only
commit. It collects reviewable shadow evidence without changing ARM state,
installing a LaunchAgent, reading Keychain, calling a Private API, sending a
notification, or reaching a broker write endpoint.

## One observation

`scripts.h11_auto_v4_g020_shadow_observer.py` performs one unauthenticated
Public M1 kline request. It selects the latest candle complete for at least 10
seconds, hashes the canonical in-memory candle, and discards the raw candle.
The local ledger holds only the UTC slot key and digest; it never stores price,
direction, probability, headers, credentials, or broker identifiers.

The observer has no retry loop. A duplicate completed slot is a no-mutation
outcome. After 20 unique slots it stops before any further Public request.

## Evidence and gate

The local ledger emits canonical `H11_V4_G020_SHADOW_EVIDENCE_NO_POST_V1`
evidence. The G020 commissioning artifact requires 20 distinct slot digests,
zero abnormal statuses, zero writes and POSTs, predecessor canary evidence,
and independent Architecture/Safety/Operations CLEAR. Even then it returns
`READY_FOR_SEPARATE_LIVE_REVIEW`; it never arms a scheduler or authorizes a
broker action.

## Explicit non-goals

- Actual exit transport, cancel, close, OCO, or reconciliation.
- Persistent ARM change or unattended scheduler installation.
- Automatic promotion from shadow evidence to a live generation.
- A claim that 20 slots establish profitability or live readiness.
