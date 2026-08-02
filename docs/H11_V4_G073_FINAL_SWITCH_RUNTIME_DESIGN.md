# H-11 v4 G073 final switch runtime design

G073 is the last integration generation. G072 remains frozen and is referenced only as
incident provenance. G073 connects a resident supervisor to three-cycle reconciliation,
the frozen SHORT_V1 strategy contract, and generation/cycle/action-bound one-shot dispatchers.

`arm_state`, `release_state`, `effective_state`, `entry_gate_open`, `entry_state`,
`reconciliation_state`, `action_state`, and `exit_state` are separate values. ARM ON/OFF
changes only persisted operator intent. The resident owns fresh reconciliation and keeps
exit management independent of ARM OFF.

The resident accepts injected reconciler, strategy source, and action ports. The checked-in
bootstrap intentionally injects no external transport; therefore the implementation and its
tests cannot read credentials, call Private API, send notifications, or write to a broker.
The release-level activation that supplies reviewed live adapters remains a separate boundary.

Every reconciliation cycle and action scope has an exclusive started marker. Same-cycle and
same-action retry is rejected. Unknown, pending, stale, lock, heartbeat, dead-man, chain,
generation, or artifact inconsistencies project HALTED and close the entry gate.

Initial activation is represented by a fake-only ordering contract. It is not executed by
operation 60, and no G073 capability is enabled until a separately authorized transaction
has produced a PASSED outcome.
