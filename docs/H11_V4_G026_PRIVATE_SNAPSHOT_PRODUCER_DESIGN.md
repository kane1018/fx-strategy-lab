# H-11 v4 G026 one-use Private GET snapshot producer

G026 adds one reviewed producer that can perform exactly one signed GET to each
of `latestExecutions`, `openPositions`, and `activeOrders`. It stores only
sanitized counts and flat/zero-active booleans in an inert, generation-bound
controller artifact. It cannot call a broker write route, issue a permit,
change persistent ARM state, send a notification, or install a LaunchAgent.

The producer creates an `O_EXCL` started marker under the generation-specific
Application Support state root before credential access or network use. Any
failure after that marker is terminal for the generation; the marker is never
deleted or reset and no retry is permitted. Success writes canonical evidence
and an `O_EXCL` passed marker, bound to reviewed-files digest, generation
digest, controller cycle, and a maximum 45-second validity window.

The offline controller remains a separate process with no HTTP, Keychain,
Private API, notification, permit, ARM mutation, or broker transport import.
It loads only the canonical inert artifact. Missing evidence retains
`ACCOUNT_SNAPSHOT_UNKNOWN`; incomplete, failed, stale, substituted, or
cross-generation evidence fails closed.

Implementation and fake-only tests do not execute Keychain access or network
requests. The real producer invocation remains separately generation-bound
after G026 review, refreeze, commit/push, and fresh shadow commissioning.
