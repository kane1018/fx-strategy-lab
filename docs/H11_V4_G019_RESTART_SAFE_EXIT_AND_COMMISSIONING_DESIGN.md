# H-11 v4 G019 restart-safe exit / commissioning design

## Status

This document defines a no-POST design candidate. It does not activate a
generation, issue a permit, read credentials, call a Private API, install a
LaunchAgent, change persistent ARM state, or authorize a broker write.

The currently traded G018 generation and a future 30-minute generation must
not share a generation label. The 30-minute candidate is therefore G019.

## Confirmed problems

1. The monitor process can create a scheduled-exit marker but cannot execute
   the position-specific close itself.
2. The foreground lifecycle driver owns the actual exit dispatcher. Losing
   that process can leave a protected position without an active dispatcher.
3. The actual transport consumes a process-memory activation permit and keeps
   write ordering in process memory. Reconstructing it after a crash is not a
   safe restart mechanism.
4. Current generation validation requires `actual_post_authorized=false`,
   `live_ready=false`, and `unattended_live_supported=false`, while the
   unattended scheduler requires the latter two values to be true. A distinct
   commissioning artifact is required; the frozen research/canary generation
   must not double as live authorization.

## G019 exit proposal under test

- Signal horizon: 30 minutes.
- Maximum hold: exactly 30 completed M1 bars after fill.
- Stop: 1.50 times frozen completed-H1 ATR(24) from actual average fill.
- Take profit: 1.50R from actual average fill.
- BUY exits use executable BID; SELL exits use executable ASK.
- If stop and target are both touched in the same M1 bar, research resolves
  the collision as stop-first.
- Maximum accepted entries per JST trading day: 30, sequential and only after
  flat.
- Earlier stop conditions still dominate the entry-count limit:
  JPY 10,000 daily realized loss, JPY 50,000 monthly realized loss, or five
  consecutive losses.

The pure implementation is
`backend/app/h11_auto/v4_gmo_g019_exit_policy.py`. It does not establish
positive expected value. The exact rule still requires reproducible BID/ASK
backtesting and out-of-sample acceptance before live commissioning.

## Restart-safe target architecture

The target is a finite scheduled tick, not a foreground process that waits for
up to the holding period:

1. Entry and exact-size OCO complete under the existing single-attempt action
   rules.
2. The coordinator durably records exact protection, no pending transport
   action, generation digest, a non-identifier cycle-binding digest, scheduled
   exit time, and the previous finite observation time.
3. The entry process exits after the durable protected state is confirmed.
4. A generation-bound finite worker wakes periodically, reads only local
   durable state, and compares the persisted scheduled-exit timestamp with its
   timezone-aware observation timestamp inside the reviewed decision module.
   Cycle binding must match and the observation gap must not exceed 60 seconds.
5. Before the exit deadline it reports a no-write monitoring tick.
6. At the exit deadline it may only report that a separate one-use exit scope
   is required.
7. A future reviewed implementation must atomically claim that scope, perform
   at most one position-specific close attempt, reconcile once, and permanently
   halt on unknown outcome.

`h11_v4_unattended_exit_recovery_no_post.py` implements only steps 4-6 as a
pure decision. It deliberately cannot be used as a boolean allow bridge and
always returns `broker_post_authorized=false`.

## Commissioning boundary

Commissioning evidence is separate from the frozen generation. It uses schema
`H11_V4_G019_COMMISSIONING_NO_POST_V1`, a canonical artifact digest, and a
separate canonical `H11_V4_G019_SHADOW_EVIDENCE_NO_POST_V1` artifact. The
shadow artifact must contain at least 20 distinct sanitized completed-slot
digests, zero abnormal statuses, zero broker writes, and zero POST attempts.
A candidate requires all of:

- a new G019 frozen generation plus a distinct entry-disabled commissioning
  artifact, both bound to matching reviewed/generation digests; the existing
  post-canary `entry_disabled` field must not be reused for this purpose;
- completed and flat-reconciled prior canary;
- account-wide zero-active-orders evidence;
- at least 20 clear shadow scheduler cycles;
- shadow evidence bound to the same reviewed-files and generation digests;
- restart-safe exit contract and notification contract evidence;
- independent Architecture, Safety, and Operations CLEAR results.

Even complete evidence only produces
`READY_FOR_SEPARATE_LIVE_REVIEW`. It does not change ARM state and does not
authorize a broker POST. The pure gate is
`h11_v4_unattended_commissioning_no_post.py`.
The current fail-closed artifact is
`docs/templates/h11_v4_g019_commissioning_no_post.json`; it is self-digested,
Its bound shadow artifact is
`docs/templates/h11_v4_g019_shadow_evidence_no_post.json`; it currently has no
completed-slot digests and is also fail-closed.

The reviewed shadow-evidence producer is not implemented in this phase.
Accordingly, `SHADOW_EVIDENCE_PRODUCER_IMPLEMENTED` is fixed to `False` and
`READY_FOR_SEPARATE_LIVE_REVIEW` is intentionally unreachable. A future
reviewed phase must implement the producer and bind exact G018 predecessor
generation, reconciliation-artifact, and handoff digests before changing that
constant.

## Explicitly not implemented

- Actual restart-safe close transport or a persisted exit permit.
- Private reconciliation after process restart.
- LaunchAgent installation for the exit worker.
- Scheduler or UI wiring to commissioning evidence.
- Persistent ARM ON.
- G019 generation freeze, external preparation, or live activation.
- Any broker GET/POST, credential access, or notification send.

These remain review-gated phases. The next implementation may not reuse the
entry permit, synthesize an allow boolean, use a generic opposite close, retry
an unknown write, or infer broker identifiers.

## G022 fake-only durable claim implementation

`h11_v4_unattended_restart_safe_exit_no_post.py` now implements the local
portion of this contract: a SQLite-backed one-use scope claim and a pure
synthetic outcome input. It invokes no executor. Completion requires a known
synthetic flat result; unknown, non-fake, duplicate, mismatched-generation,
or restart-after-claim outcomes persist a halt. It has no actual transport,
credential, Private API, notification, LaunchAgent, or scheduler dependency.
A future actual-close phase must be separately reviewed and may not replace
this claim-before-attempt / unknown-halt behavior.

The historical G018 reconciliation marker lacks a cross-marker digest binding.
Its local facts may be inspected as historical context, but the predecessor
binder refuses it as commissioning evidence. Only a reconciliation format
whose started and passed markers both bind the same origin and target
generation, and whose passed marker binds the exact started-marker digest, may
produce a canonical predecessor completion artifact.

If the local SQLite store itself is unavailable, the fake-only module reports
`STORAGE_UNAVAILABLE_NO_POST` and does not apply an outcome. It deliberately
does not claim that a durable halt was recorded when storage was unavailable.
A future actual-close phase must refuse before any transport boundary unless
durable storage is known available.
