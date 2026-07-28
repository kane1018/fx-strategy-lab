# H-11 v4 predecessor completion evidence V2 design

## Scope and status

This is a no-broker, no-notification design for the evidence format that a
future fresh post-canary reconciliation may produce. It does not alter G018
runtime files, read credentials, call a Private API, install a LaunchAgent,
change persistent ARM state, issue a permit, or authorize any broker action.

G018's historical markers remain read-only historical context. They lack the
required cross-marker target binding and must remain ineligible for
commissioning.

## V2 marker contract

A future reconciliation producer may write exactly one `started` marker before
its separately authorized reconciliation operation. The marker must contain
only:

- `schema`: a new, versioned V2 reconciliation schema;
- `origin_generation_digest`: the completed canary generation;
- `target_generation_digest`: the exact reconciliation generation;
- `broker_write_attempt_count: 0`.

If that future reconciliation reaches a known, flat, zero-active result, it
may write exactly one `passed` marker containing:

- the same V2 schema;
- the same origin and target generation digests as `started`;
- `started_marker_digest`: SHA-256 of the exact immutable `started` file;
- only sanitized result booleans and aggregate read/write counts;
- `raw_response_retained: false` and `identifier_exposed: false`.

The target digest must also equal the runtime directory digest. Any mismatch,
missing field, duplicate candidate, symlink, unexpected schema, nonzero write
count, unknown result, non-flat result, or active order causes fail-closed
rejection.

## Canonical predecessor artifact

The no-POST binder may read the origin coordinator ledger with SQLite
`mode=ro` and the two V2 marker files. It derives a canonical artifact from
the exact local files and records only hashes, boolean completion facts, and
aggregate counts. It must not store broker identifiers, raw responses,
credentials, headers, signatures, or prices.

The artifact is evidence only. Its boolean conversion is false, it must not
be accepted as a transport allow value, and it cannot change persistent ARM.

## Commissioning boundary

Even a valid V2 predecessor artifact is insufficient by itself. Commissioning
also requires a separate reviewed generation, shadow evidence, restart-safe
actual exit evidence, notification evidence, and independent Architecture,
Safety, and Operations CLEAR reviews. Until a separately reviewed phase
changes the fixed fail-closed commissioning gates, the result remains
`NOT_READY` with `broker_post_authorized=false` and `actual_post_count=0`.

## Required future implementation order

1. A synthetic-only producer writes the isolated
   `H11_V4_PREDECESSOR_COMPLETION_V2_FAKE_ONLY_V1` pair for shape and
   cross-binding tests. Its marker names and schema are intentionally rejected
   by the commissioning binder.
2. Implement the separate actual V2 producer only after a new review; it must
   retain the same cross-binding but may not reuse the synthetic schema or
   marker names.
3. Add binder acceptance and rejection tests using temporary synthetic files.
4. Perform independent Architecture, Safety, and Operations review.
5. Freeze a new reviewed generation and create fresh external evidence only
   under separate operator authorization.
6. Keep G018 markers untouched and do not backfill, migrate, or infer V2
   evidence from legacy files.

## Fresh-evidence design boundary

The first non-synthetic V2 producer must be generation-bound and one-use. It
may be considered only after the reviewed generation, its reconciliation
contract, and all independent reviews are frozen together. Its future
external evidence operation must begin from a clean main worktree and must not
reuse G018 facts, markers, confirmation, credentials, notification outcomes,
or broker results. This document does not authorize that operation.

No actual reconciliation, broker access, notification, ARM operation, or
commissioning activation is authorized by this document.
