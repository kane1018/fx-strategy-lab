# H-11 v4 Final Single-Generation Completion Design

Status: DESIGN FROZEN BEFORE FINAL GENERATION

Target successor: `H11_AUTO_30M_20260802_G070`

Baseline: G069 remains immutable incident and commissioning provenance. No G069
marker, HALT, state root, digest, or operation outcome is reused as G070
authorization.

## 1. Goal

After one release-level activation, the operator controls unattended live
operation with only the UI ARM ON/OFF switch:

- ARM ON records operating intent. It does not place an order.
- The resident runtime evaluates the frozen strategy, market, risk, freshness,
  ownership, protection, and account gates.
- A broker action is possible only for an exact reviewed action plan and a
  cycle/action-bound one-use scope.
- ARM OFF blocks new entries but never stops protection, take-profit,
  stop-loss, time exit, or flat reconciliation for an owned position.
- No daily authorization and no per-trade confirmation are required after the
  one release-level activation.

The final generation is not created until every component and transition in
this document is included in its reviewed-files digest.

## 2. Confirmed G069 Gap

G069 correctly fails closed, but its completion order is circular:

1. Missing fresh account reconciliation projects `HALTED`.
2. ARM ON rejects `HALTED`.
3. The available Private GET entrypoint is the historical G026 script. It
   requires sealed shadow artifacts and is not a G069 release-runtime path.
4. Adding a current-generation producer after operation 60 changes the
   reviewed-files digest and invalidates the one-use commissioning result.
5. A one-time snapshot also expires; G069 resident does not refresh it.

G070 must therefore include the producer, recurring read-only reconciliation,
runtime projection, action scopes, exit management, UI contract, operation 60,
and release activation before its digest is frozen.

## 3. Non-Circular State Model

The following dimensions are independent and must never be collapsed into one
boolean:

### 3.1 Control plane

- `READY`: exact generation/digest, one resident owner, fresh heartbeat,
  dead-man alive, fresh chain, no persistent HALT, no pending transport.
- `HALTED`: digest mismatch, duplicate owner, stale heartbeat, dead-man failure,
  malformed evidence, pending/unknown write, or persistent HALT.

### 3.2 Reconciliation

- `REQUIRED`: no fresh account observation yet. Safe startup state, not a
  persistent HALT.
- `IN_PROGRESS`: one current slot is being observed. Entry remains closed.
- `FRESH_FLAT`: zero positions and zero active orders are explicitly observed.
- `FRESH_PROTECTED`: an owned position has exact quantity and exact protection.
- `STALE`: the last valid observation exceeded its maximum age.
- `UNKNOWN`: inconsistent, malformed, pending, or unowned account state.

`REQUIRED` and `IN_PROGRESS` permit read-only recovery. They never permit an
entry. `STALE` and `UNKNOWN` fail closed; `UNKNOWN` latches persistent HALT.

### 3.3 Operator intent

- `OFF`
- `ON`

ARM state is persistent and generation/digest-bound. It is not a broker POST
authorization and is not consumed per day or per trade.

### 3.4 Effective runtime state

- `OFF`: ARM OFF and no owned position.
- `RECOVERING`: control plane is ready while reconciliation is REQUIRED or IN
  PROGRESS. Entry gate is false.
- `ON_WAITING`: ARM ON plus FRESH_FLAT. Signal/risk/market gates remain separate.
- `ON_EXIT_ONLY`: ARM ON plus FRESH_PROTECTED. Entry gate is false.
- `EXIT_ONLY`: ARM OFF plus FRESH_PROTECTED. Exit management remains active.
- `HALTED`: the safe state cannot be proven.

### 3.5 Entry state

- `DISARMED`
- `RECOVERING_RECONCILIATION`
- `WAITING_FOR_SIGNAL`
- `ENTRY_GATES_BLOCKED`
- `ACTION_IN_PROGRESS`
- `POSITION_OPEN`
- `HALTED`

`entry_gate_open` is true only when all of these are true:

- control plane READY
- reconciliation FRESH_FLAT
- ARM ON
- no owned/open position and no active order
- frozen strategy emits an actionable fresh signal
- risk, time, market, spread, freshness, and daily limits pass
- no cycle/action marker already exists

## 4. Current-Generation Read-Only Reconciliation

G070 receives a dedicated producer and resident reader. The G026 CLI is not
called, wrapped, aliased, or imported as the operational entrypoint.

The reader contract is:

- exact G070 label, generation digest, and reviewed-files digest
- Keychain values remain internal and are never rendered or persisted
- `latestExecutions`, `openPositions`, and `activeOrders` are each read once per
  distinct reconciliation slot
- no same-slot retry
- the next slot is a new observation, not a retry of the prior slot
- a slot marker is created with O_EXCL before credential or network access
- raw responses and identifiers exist in memory only
- persisted output contains sanitized counts, booleans, timestamps, slot key,
  artifact digest, and hash-chain predecessor only
- broker POST/write count remains zero

The default slot is 30 seconds and the maximum evidence age is 60 seconds.
One failed read does not erase a still-fresh prior observation. No new entry is
allowed after freshness expires. A pending or internally inconsistent account
result latches HALT immediately.

For an open position, the in-memory reconciler must derive all three values
from broker observations and the local coordinator ownership record:

- `ownership_exact=true`
- `quantity_matches=true`
- `protection_confirmed=true`

Counts alone are never sufficient. If any value is false or unknown, the
state is HALTED and entry remains closed. Only sanitized booleans are stored.

## 5. Resident Runtime

One launchd-owned resident supervisor performs these phases sequentially:

1. verify canonical generation, reviewed digest, evidence, and attestation
2. acquire the single process lock
3. update heartbeat, dead-man, and heartbeat chain
4. run the due read-only reconciliation slot
5. project ARM/effective/reconciliation/entry states
6. if an owned position exists, run protection and exit management only
7. if flat and ARM ON, evaluate the frozen signal and entry gates
8. if actionable, create one exact action scope and invoke the existing
   coordinated actual path
9. reconcile once after each distinct action
10. write only sanitized runtime status

The UI process is not part of this loop. Closing or restarting the UI cannot
stop the resident runtime.

The supervisor must handle Mac restart, sleep resume, Ctrl-C, and exceptions:

- recover only from an expired owner lock whose PID is proven absent
- start in reconciliation REQUIRED, not in a false flat state
- continue exit management while ARM is OFF
- latch HALT for unknown write outcome, ownership mismatch, unprotected
  position, duplicate worker, digest mismatch, or dead-man failure
- never auto-clear a persistent HALT

## 6. Release-Level Activation and POST Boundary

G070 has exactly one initial release activation. This is not a daily or
per-trade approval.

The release activation operation:

1. requires canonical G070, clean trusted commit, external A/S/O CLEAR, and
   operation 60 PASSED
2. writes an O_EXCL started marker before Keychain or network access
3. performs one fresh reconciliation group
4. requires FRESH_FLAT or FRESH_PROTECTED
5. records a generation/digest-bound release capability artifact
6. leaves ARM unchanged
7. performs no broker POST and places no order

At rest, `actual_post_authorized=false`. ARM ON never changes that field.

For each broker action, the runtime creates an opaque, cycle/action-bound,
one-use scope only after all current gates pass. The concrete reviewed actual
transport accepts that scope, verifies exact generation, action, side, symbol,
quantity, coordinator row, and O_EXCL marker, then calls the existing hard
guard with a literal `True` inside that concrete call. There is no exported
generic allow boolean, no environment unlock, and no reusable allow bridge.

Each action is independently one-attempt:

- MARKET entry: maximum one attempt
- exact-size protection OCO: maximum one attempt after known fill quantity
- partial pending cancellation: maximum one attempt when independently needed
- time-exit OCO cancellation: maximum one attempt
- position-specific close: maximum one attempt

Unknown outcomes latch HALT. No same-action retry or repost is allowed.

This concrete action-scope design requires an explicit project-policy review
because current repository policy rejects a generic allow bridge. The policy
must authorize only this exact G070 capability path; it must not weaken or
remove the hard guard.

## 7. Position and Exit Contract

- A fill is never called protected until exact OCO protection is confirmed.
- A position always closes the entry gate.
- Natural OCO settlement is reconciled to flat without an extra POST.
- The 30-minute dispatcher uses the existing exact OCO cancel and
  position-specific close sequence, each at most once.
- ARM OFF does not cancel the exit dispatcher.
- After flat reconciliation, ARM ON returns to ON_WAITING and ARM OFF returns
  to OFF.
- Unknown ownership, quantity, protection, or action outcome is HALTED.

## 8. UI and Safe API Contract

The API returns these fields independently:

- `arm_state`
- `control_plane_state`
- `reconciliation_state`
- `effective_state`
- `entry_gate_open`
- `entry_state`
- `safe_reason_label`

The UI rules are:

- ON/OFF buttons are disabled only when the current contract cannot be loaded
  or the requested state write cannot be generation-bound safely.
- Missing fresh reconciliation does not disable ARM ON. It displays
  RECOVERING and keeps entry closed until the resident obtains fresh evidence.
- A protected owned position with ARM ON displays ON_EXIT_ONLY.
- ARM OFF remains available while HALTED, but does not stop exit management.
- UI restart reloads persisted ARM intent and resident status.
- No UI route imports or calls broker transport.

## 9. G070 Implementation Scope

The final generation must include, before digest calculation:

- G070 generation contract and artifact validators
- G070 resident supervisor and operation 60
- G070 current-generation reconciliation reader, slot store, and projection
- G070 release-level activation operation
- G070 cycle/action scope and concrete hard-guard binding
- scheduler plist rendering and exact binding
- ARM API projection and UI state rendering
- restart, lock, dead-man, heartbeat, and chain handling
- entry orchestration integration
- protection and 30-minute exit integration
- all focused, related, API, UI-contract, restart, and fake-transport tests
- reviewed-files registry entries
- candidate manifest, commissioning evidence, and A/S/O attestation
- this frozen design document

Historical generation-specific compatibility code is not refactored during
G070 unless a direct import blocks the G070 path. `backend/app/main_readonly.py`
is not changed.

## 10. Validation Matrix Before Any One-Use Operation

All tests use fake/synthetic clients and no real credential or broker I/O.

Required checks:

- state dimensions remain independent
- operation 60 passes with reconciliation REQUIRED and entry closed
- REQUIRED/IN_PROGRESS are not persistent HALT
- stale/unknown/digest mismatch/duplicate worker/dead-man failure are HALTED
- initial release activation is one-use and no-POST
- recurring reconciliation is one attempt per distinct slot
- same-slot retry is rejected
- flat projection becomes ON_WAITING only with ARM ON
- protected owned position becomes ON_EXIT_ONLY or EXIT_ONLY
- unconfirmed position is HALTED
- ARM OFF continues protection and exit handling
- UI absence does not stop resident updates
- restart/sleep/Ctrl-C recovery is fail-closed
- daily authorization is absent from the G070 call graph
- human confirmation phrases are absent from the G070 call graph
- exact action scopes cannot be reused or cross-bound
- fake MARKET, OCO, cancel, close, and natural settlement paths are exact-once
- actual transport cannot run without the opaque action scope
- hard guard remains default-deny outside the concrete scoped call
- broker write imports are absent from UI, reconciliation, and control-plane
  modules
- Ruff, diff check, danger scan, and independent A/S/O are CLEAR
- reviewed-files digest, generation digest, evidence, and attestation cross-bind

The full synthetic end-to-end acceptance sequence is:

`operation60 -> release activation -> ARM ON -> wait -> fake entry -> fake OCO -> ARM OFF -> fake time/natural exit -> flat reconciliation`

It must complete without daily authorization or a confirmation phrase.

## 11. One-Time Operational Sequence

No external or one-use operation may begin before the implementation is
complete and immutable.

1. implement all G070 paths in one candidate worktree
2. run focused and related tests, Ruff, diff check, and danger scan
3. run independent Architecture/Safety/Operations review
4. fix all findings while G070 is still an uncommissioned candidate
5. recalculate and cross-bind all artifacts
6. commit and push the implementation
7. promote the exact G070 candidate to the canonical manifest
8. commit and push the promotion; require clean trusted main
9. run G070 operation 60 exactly once
10. verify resident control-plane readiness
11. run G070 release activation exactly once, including the initial fresh
    read-only reconciliation
12. verify release capability and fresh reconciliation
13. set local ARM ON once
14. verify the expected effective state and resident independence
15. stop; the resident runtime subsequently decides when conditions permit a
    trade

Operation 60 performs no Private GET and accepts reconciliation REQUIRED as a
safe, entry-closed commissioning state. This ordering removes the G069 cycle.

## 12. No-Loop Rules

- G069 is frozen now.
- G070 is the only planned successor.
- No operation 60, Private GET, Keychain access, notification, or broker action
  occurs while G070 source or artifacts can still change.
- Deterministic failures before operation 60 are fixed within the unconsumed
  G070 candidate, followed by full validation and digest recalculation.
- After the G070 operation 60 started marker exists, code is not changed and
  operation 60 is never retried.
- A G070 external-operation failure is reported and preserved. No G071 is
  created automatically.
- Historical markers and evidence are provenance only, never authorization.
- A blocker never grants permission to widen scope or bypass a gate.

## 13. Phase Boundaries

This document completes only the design-freeze phase. It performs no broker
GET/POST, Keychain access, notification, ARM mutation, LaunchAgent mutation,
commit, push, or generation creation.

The next phase is one bounded G070 implementation batch through fake-only
validation and A/S/O review. Real operation 60, release activation, ARM ON, and
broker-capable runtime activation remain later explicit operational boundaries.
