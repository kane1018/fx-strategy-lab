# H-11 v4 G075 Runtime-only Corrective Contract

## Status

This document freezes the only accepted correction after the terminal G074
initial-activation incident. G074 and all of its operation, transaction, HALT,
marker, runtime, and review evidence remain immutable provenance only. None of
them authorizes G075. G075 uses a distinct digest and state root, and no G076
fallback is part of this plan.

The exact application `httpx` public path completed successfully after the G074
failure. The predecessor failure is therefore classified only as transient or
request-specific. G075 does not weaken TLS, disable verification, add fallback
transport, or retry the G074 request.

The implementation phase is fake-only. It must not read the real Keychain,
call a real Private API, mutate ARM, change LaunchAgent state, send a
notification, or perform a broker action. Runtime commissioning and initial
activation remain separate, explicitly authorized operations after review.

## Completion definition

The system is complete only when an operator can repeatedly select ARM ON or
ARM OFF in the UI and the resident runtime continues safely without daily or
per-trade human approval.

- ARM ON changes only durable operating intent.
- ARM OFF closes the new-entry gate but never stops protection, take-profit,
  stop-loss, time exit, or flat reconciliation for an owned position.
- The UI does not call Keychain, Private GET, or broker transport.
- The resident runtime obtains fresh reconciliation before opening an entry
  gate or managing a recovered position.
- A broker action is possible only through the existing default-deny hard
  guard after exact generation, release, cycle, reconciliation, and one-use
  action scope checks.
- Unknown, pending, stale, malformed, mismatched, or conflicting state is
  HALTED and never interpreted as authorization.

## Immutable safety boundary

G075 must not:

- modify `backend/app/main_readonly.py`;
- weaken or bypass `assert_real_broker_post_allowed`;
- add a reusable boolean allow bridge;
- enable live operation through environment variables or `.env`;
- infer or alter symbol, direction, quantity, execution type, protection, or
  exit policy outside the frozen strategy artifact;
- retry or repost the same broker action;
- reuse G073 authorization, state root, marker, reconciliation, or operation
  evidence;
- persist raw account responses, credentials, headers, signatures, or broker
  identifiers;
- treat ARM state, release state, reconciliation state, entry gate, or action
  authorization as the same value.

## State model

The following values are independent and must be projected independently:

- `arm_state`: `OFF` or `ON`.
- `release_state`: `LOCKED` or `ENABLED`.
- `effective_state`: `OFF`, `ON_WAITING`, `ON_EXIT_ONLY`, `EXIT_ONLY`, or
  `HALTED`.
- `entry_gate_open`: boolean.
- `entry_state`: `DISABLED`, `WAITING_FOR_RECONCILIATION`,
  `WAITING_FOR_SIGNAL`, `ACTION_IN_PROGRESS`, `BLOCKED_POSITION_OPEN`, or
  `HALTED`.
- `reconciliation_state`: `REQUIRED`, `FRESH_FLAT`, `FRESH_PROTECTED`,
  `STALE`, or `UNKNOWN`.

### Projection rules

| Inputs | Effective state | Entry gate |
| --- | --- | --- |
| release locked | HALTED | false |
| runtime unhealthy or reconciliation unknown | HALTED | false |
| ARM OFF and fresh flat | OFF | false |
| ARM OFF and fresh protected owned position | EXIT_ONLY | false |
| ARM ON and reconciliation required/stale | HALTED | false |
| ARM ON and fresh flat | ON_WAITING | strategy gate only |
| ARM ON and fresh protected owned position | ON_EXIT_ONLY | false |
| any unconfirmed ownership, quantity, or protection | HALTED | false |

## Durable release and switch capability

The initial G075 activation is a one-shot transaction. It creates the durable
release and switch capability only after all steps complete successfully. A
capability is valid only when all of the following match:

- exact G075 generation label and generation digest;
- exact reviewed-files digest;
- exact release transaction outcome `PASSED`;
- exact capability artifact digest;
- exact operation 60 `PASSED` evidence;
- regular-file, non-symlink markers with the expected schema;
- no persistent HALT.

An `UNKNOWN`, timeout, malformed artifact, partial transaction, or HALT leaves
the release locked. UI ON is rejected without changing ARM state or invoking
external operations.

After the initial transaction passes, UI OFF and UI ON validate the durable
capability and mutate only arm intent. They do not rerun initial activation,
read Keychain, reconcile the account, or call broker transport.

## Resident reconciliation

The resident runtime owns reconciliation. Each scheduled cycle has a unique,
generation-bound cycle identifier and one-use started/outcome markers.

- `latestExecutions`, `openPositions`, and `activeOrders` are attempted at
  most once each per cycle.
- The same cycle is never retried.
- A later scheduled cycle is a new observation, not a retry.
- Partial failure records exact attempt counts and becomes `UNKNOWN`/HALTED.
- Only sanitized counts and ownership/quantity/protection booleans persist.
- A position is actionable for exit management only when ownership,
  quantity, and protection are explicitly true.
- A position always closes the entry gate.

## Opaque action scope

No action is authorized by a boolean assembled from readiness flags. G075
uses a non-boolean, non-coercible, generation-bound action scope containing:

- generation and reviewed-files digests;
- release capability digest;
- reconciliation artifact digest and cycle identifier;
- frozen strategy artifact digest;
- exact action kind;
- exact symbol and quantity;
- exact side only when supplied by the frozen strategy decision;
- issue and expiry times;
- unique one-use action key.

The scope is valid only for one exact action. The action start is persisted
before transport. Known completion and unknown completion are terminal. There
is no same-action retry or repost.

## Restart and exit recovery

Restart never restores in-memory transport sequence state as authorization.
It first performs fresh reconciliation. Recovery is allowed only from durable,
cross-bound evidence that proves:

- the position is owned by this generation;
- quantity exactly matches the frozen position quantity;
- exact protection is confirmed;
- the predecessor entry/protection actions have known terminal outcomes;
- no action is pending or unknown;
- the recovery scope matches the current generation, release capability,
  reconciliation, and action.

ARM state is irrelevant to permission for a risk-reducing exit. ARM OFF with
an owned protected position is `EXIT_ONLY`; ARM ON with that position is
`ON_EXIT_ONLY`. Both prohibit entry and continue protection and exit handling.

Malformed lock, a live duplicate worker, stale heartbeat, stale dead-man,
heartbeat-chain mismatch, digest mismatch, unknown action, or unconfirmed
position ownership produces HALTED.

## UI contract

- ON/OFF controls are disabled only when the current generation contract
  cannot be loaded safely.
- Before release activation, ON returns a safe refusal and makes no mutation.
- After release activation, ON/OFF changes only persisted arm intent.
- Signal, flatness, and entry gate are not prerequisites for storing ON intent.
- The UI displays all independent states and a safe HALT label.
- UI process lifetime does not control resident process lifetime.
- UI restart reloads persisted intent and resident status.

## Required fake-only acceptance matrix

G075 is not reviewable until deterministic fake tests prove all of the
following in one candidate generation:

1. initial activation success enables durable switch capability;
2. initial activation unknown leaves it disabled;
3. UI OFF to ON does not repeat activation or perform external reads;
4. ARM ON plus fresh flat reaches ON_WAITING;
5. ARM ON plus owned protected position reaches ON_EXIT_ONLY;
6. ARM OFF plus owned protected position reaches EXIT_ONLY;
7. unconfirmed position state reaches HALTED;
8. restart requires fresh reconciliation before entry;
9. restart can resume only verified risk-reducing exit management;
10. duplicate worker, stale heartbeat, dead-man failure, chain mismatch,
    malformed/symlink state, and digest mismatch reach HALTED;
11. each reconciliation endpoint is attempted at most once per cycle;
12. each broker action is attempted at most once with terminal unknown state;
13. no daily authorization or per-trade phrase exists;
14. broker POST, Private API, credential, notification, and ARM mutation counts
    remain zero during implementation tests;
15. the existing hard guard remains default-deny and no allow bridge exists.

## Irreversible execution order

After implementation, tests, digest calculation, and independent A/S/O review
are all clear, the only allowed operational sequence is:

1. commit and push the reviewed G075 implementation;
2. promote the exact G075 artifact and commit/push promotion;
3. execute G075 operation 60 once;
4. verify resident readiness;
5. execute the G075 initial activation transaction once;
6. verify durable switch capability and safe runtime projection;
7. stop before any broker POST unless a separate activation boundary is
   explicitly approved.

Operation 60 or initial activation `UNKNOWN` is terminal for G075. No retry,
marker reset, or automatic successor generation is permitted.

## Definition of done

G075 is complete only when the fake acceptance matrix, related tests, Ruff,
diff check, danger scan, and independent Architecture/Safety/Operations review
are all clear; artifacts and digests cross-bind; and the implementation has no
unresolved path that would require another generation after operation 60.
