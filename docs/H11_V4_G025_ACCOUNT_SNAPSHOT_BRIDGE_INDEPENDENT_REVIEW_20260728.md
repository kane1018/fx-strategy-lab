# H-11 v4 G025 bound account-snapshot bridge independent review

## Scope

This record covers the G025 no-POST bridge from a sanitized account snapshot
to the integrated unattended-controller evidence boundary.

Reviewed files digest:
`sha256:e6a9fd6429d3f2ebbe610113d679a84e42d48ddb0f7f69c862437e34adb48e71`

Generation digest:
`sha256:7117c2ecf4093ee608921ef74d8e4763bc8f95d3ab706fbe1e312a4e47a63190`

The review was read-only. It did not call a Private API, read Keychain,
send a notification, change persistent ARM state, install a LaunchAgent,
issue a permit, or reach a broker write endpoint.

## Implemented boundary

- The controller-facing account snapshot is an inert, canonical artifact.
- The artifact binds the reviewed-files digest, generation digest, controller
  cycle, observation window, and a canonical operation marker.
- The marker requires exactly three broker GET observations, zero broker
  writes, and zero broker POSTs.
- The integrated snapshot carries the full inert artifact. A digest alone
  cannot claim that the account snapshot is known.
- The durable SQLite store consumes each account-snapshot artifact once.
- Reuse persists a generation HALT, and a restarted store restores the
  sanitized original HALT reason.
- Missing evidence preserves the legacy fail-closed
  `ACCOUNT_SNAPSHOT_UNKNOWN` path.

## Independent decisions

### Architecture: CLEAR

The canonical marker and envelope close the previous arbitrary-marker gap.
The assembler and integrated store validate the same review, generation,
cycle, freshness, digest, and account-state bindings. Cross-cycle reuse and
direct forged-digest injection are rejected.

### Safety: CLEAR

The controller imports only the inert evidence type and validator. It has no
HTTP client, credential loader, Keychain access, notification transport,
permit, broker transport, or write authorization. Decisions remain
non-truthy with `broker_write=false` and `actual_post_count=0`.

### Operations: CLEAR

One-use consumption is SQLite-backed across process restarts. Persistent HALT
restores a fixed-format sanitized cause and rejects a reviewed-boundary
mismatch. Storage unavailability remains fail-closed and never claims that a
HALT was durably persisted.

## Verification

- Focused account-snapshot/controller suite: 80 passed.
- Broader unattended suite before bounded interruption: 321 passed; one
  expected-value mismatch was corrected for restored HALT-cause reporting.
- Ruff: passed.
- `git diff --check`: passed.
- Danger scan for live/write/credential dependencies in controller modules:
  passed.

## Promotion limit

This CLEAR record covers only the no-POST evidence bridge. It does not prove a
live Private GET producer, notifications, persistent ARM readiness, entry or
exit transport readiness, profitability, or broker POST authorization.
