# Current-generation shadow commissioning (no POST)

This path records at most 20 distinct completed Public `USD_JPY` M1 slots for
the currently frozen generation. The local ledger stores only opaque digests;
it never stores prices, direction, credentials, Private API responses, or any
broker authority. A separate local sealing command requires the generation's
review evidence and the canonical G018 completion binder, then writes
generation-bound shadow and commissioning artifacts under the ignored runtime
root.

`SHADOW_COMMISSIONED_NO_POST` means exactly: 20 distinct slots, zero recorded
abnormal observations, zero broker writes, canonical artifacts, and all three
review flags clear. It does not mean live ready. Persistent ARM change,
permit issuance, notification, Private API use, broker writes, and actual
post count remain fixed to false/zero.

Sealing is one-use. The command first proves shadow eligibility, validates all
review and local-validation facts, then creates a started marker and the exact
artifact pair. A pre-existing started or passed marker is a persistent halt:
the generation must not be repaired or re-sealed; create a corrective
generation and regenerate all shadow evidence instead. The no-POST controller
rechecks the sealed review-evidence digest before it accepts the pair.

Any abnormal Public observation is recorded once and immediately makes the
generation terminal for shadow commissioning. Later invocations perform no
additional Public GET and report that a corrective generation is required. A
separate generation-bound terminal marker is created before the abnormal ledger
update, so failure of that ledger write still blocks the next Public fetch.
Likewise, every failure after the one-use seal started marker is created is
reported on that first invocation as a persistent halt requiring a corrective
generation; a partially written artifact set is never repaired or re-sealed.
