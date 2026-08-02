# H-11 v4 G072 switch-control design

G072 is the final runtime-only corrective generation for the repeated switch-control contract. It does not
re-run or authorize G070/G071 evidence. Predecessor references are incident provenance only.

## Contract

`arm_state`, `release_state`, `effective_state`, `entry_gate_open`, `entry_state`, and `reconciliation_state`
are separate persisted or projected concepts. ARM ON changes operating intent only. It does not call a
broker transport, Private API, Keychain, notification, or entry evaluator.

Before the first successful G072 atomic activation, the UI ON action is rejected without mutating ARM state.
The one-shot transaction is the only path that can create the durable switch-control capability. A successful
transaction is not executed in this implementation phase; it is covered only by injected fake readers,
mutators, and projection waiters.

After that capability exists, UI OFF and UI ON only change persisted ARM intent. The resident supervisor owns
fresh reconciliation. A fresh flat result projects `ON_WAITING`; an explicitly owned, quantity-matched,
protected position projects `ON_EXIT_ONLY`. An ARM OFF position projects `EXIT_ONLY`. Missing or false
ownership, quantity, or protection, stale evidence, lock conflict, dead-man failure, heartbeat failure,
pending state, unknown outcome, or digest mismatch projects `HALTED` and closes the entry gate.

For a flat `ON_WAITING` projection, the existing strategy artifact supplies a typed `G072EntryEvaluation`.
The evaluator must bind the current generation/reviewed digests and report known results for signal, risk,
market-open, spread, freshness, and limits. Only when every predicate is clear and the signal is actionable
does the runtime expose `entry_gate_open=true` and `entry_state=ENTRY_READY`; this is still not a broker
transport authorization. Missing evaluator output is a safe wait, while unknown evaluation or binding mismatch
is HALTED.

## Reconciliation

Each resident cycle has a generation-bound started and outcome marker. The three specified read-only endpoints
are each attempted at most once per cycle. A partial failure records sanitized attempt counts and becomes
UNKNOWN/HALTED; the same cycle is never retried. Raw responses, credentials, headers, signatures, and IDs are
not persisted.

## Recovery

The resident supervisor is independent of the UI. On restart it restores only persisted intent and the valid
G072 capability, then requires fresh reconciliation before opening any entry gate. A stale lock is not deleted
blindly, a duplicate worker is rejected, and heartbeat/dead-man/chain failures fail closed. ARM OFF never
stops protection, exit management, or flat reconciliation.

## Safety boundary

`live_ready`, `unattended_live_supported`, `actual_post_authorized`, and `broker_post_authorized` remain false.
This generation adds no allow bridge, no environment override, no broker-write import to the runtime engine,
and no retry/repost path. Real activation remains a separate final boundary after review and artifact
verification.
