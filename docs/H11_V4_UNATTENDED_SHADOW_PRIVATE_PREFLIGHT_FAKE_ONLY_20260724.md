# H-11 v4 Unattended Shadow Private-GET Account/Order Preflight — Slice 1, Fake-only

Date: 2026-07-24

## Objective

Begin Phase 3 of the H-11 v4 unattended track (`docs/H11_V4_UNATTENDED_SHADOW_PUBLIC_ADAPTER_NO_POST_20260724.md`'s
promotion sequence): a full operational shadow that observes real account/order
state via Private GET rather than the Phase 1 Public-only fail-closed sentinel.

This module is **slice 1 only**: it derives `broker_snapshot_fresh` /
`boot_reconciled` / `position_count` / `active_order_count` from a sanitized
Private GET of `latestExecutions` / `openPositions` / `activeOrders`. It does
**not** implement notification sending, daily/monthly/consecutive-loss-stop
tracking, host/dead-man state, operator persistent HALT, or wiring into the
shadow runner CLI. Those remain explicitly deferred (see "Deferred scope"
below).

This phase does not claim `live_ready`, `unattended_live_supported`,
`broker_post_authorized`, or performance proof. No real Keychain, Private API,
or notification capability is exercised in this pass — every test uses a fake
credential pair and a fake `httpx` transport.

## Why this is narrower than a real activation path

`backend/app/services/h11_v4_gmo_readonly_preflight.py` already implements a
reviewed, real Keychain reader + real signed Private-GET client for the same
three endpoints, but it is gated behind G013's `V4ExternalPreparationGate` /
`V4PreparationOperationPermit` preparation-ledger ceremony (reviewed-files
digest, generation manifest, operation 00–60 sequencing). The shadow
controller's own architecture is deliberately generation-independent — it has
no preparation ledger, no reviewed-files-digest binding, no operation-00–60
ceremony. Reusing `h11_v4_gmo_readonly_preflight.py` directly would either
require inventing a fake preparation-gate/permit just to satisfy its
constructor (awkward and misleading), or coupling the shadow to G013's
heavyweight ceremony (architecturally wrong for a generation-independent
controller).

So this module is a **structurally independent duplicate** of the read
sequence and response-parsing shape (mirroring the precedent
`h11_v4_gmo_readonly_preflight.py` itself set relative to the write-capable
`h11_v4_gmo_actual_transport.py`), reusing only the one genuinely stateless,
credential-store-free helper: `app.private_api.auth.build_auth_headers`.

## No real Keychain reader ships in this module, and there is no default network destination

Unlike `h11_v4_gmo_readonly_preflight.py` (which ships a real
`security find-generic-password`-based default reader),
`read_v4_unattended_shadow_private_snapshot` has **no default credential
source at all**. `V4UnattendedShadowCredentialPair` is a structural
(`Protocol`) type; the caller must always inject an already-constructed
credential pair. This means real Keychain access is unreachable from this
module's defaults — a future real-activation change would need to add an
entirely new, separately reviewed reader function, which is a natural,
obvious, and clearly-flagged diff rather than a one-line default flip.

`client: httpx.Client` is likewise a required argument with no default, and
every request path passed to `client.request(...)` is **relative**
(`/private/v1/latestExecutions`, not an absolute URL). httpx resolves a
relative path against the client's own configured `base_url`, so whatever
host the caller's client points at is the actual destination — this module
never hardcodes or falls back to `GMO_V4_PRIVATE_BASE_URL` internally. An
earlier draft of this module built an absolute URL by string-concatenating
`GMO_V4_PRIVATE_BASE_URL` with the transport path and shipped a real-host
default client when none was supplied; an independent Safety review (2026-07-24)
caught this before any external use — it meant a caller who supplied a client
with a different `base_url` (e.g. a local test server) would still have every
request routed to the real production host, and a caller who supplied no
client at all would construct a real client pointed at production regardless
of what credential pair was used. Both are fixed: `client` has no default, and
`test_requests_are_issued_against_the_callers_own_client_base_url` is a
regression test proving a non-production `base_url` is honored.

The same review round also found that the fixed 0.25-second inter-request
cadence lacked the fail-closed re-verification that `h11_v4_gmo_readonly_preflight.py`
performs after each `sleep()` call — this module originally slept for the
right duration but never confirmed the clock actually advanced, so an
interrupted or no-op sleep would silently let two Private GETs fire closer
together than intended. This is now restored (`SHADOW_PRIVATE_GET_CADENCE_NOT_REACHED`
/ `SHADOW_PRIVATE_GET_CADENCE_CLOCK_INVALID`), with
`test_cadence_fails_closed_when_sleep_does_not_advance_the_clock` proving the
fail-closed path fires and `test_cadence_sleep_is_invoked_with_the_expected_durations`
proving the normal-operation sleep durations are correct.

`test_module_reachable_app_imports_avoid_gated_and_write_capable_modules`
walks the module's static import graph and rejects any reachable `app.*`
module whose name contains an actual/canary/readonly_preflight/post_canary/
coordinator/hard_guard/launchd/notification/private_api.credentials/h11_manual
fragment.

## Composition contract

`augment_shadow_preflight_with_private_snapshot(*, base, private)` takes a
`V4GmoPreflightSnapshot` (e.g. Phase 1's fail-closed sentinel) and a
`V4UnattendedShadowPrivateSnapshot`, and replaces **only**:

- `boot_reconciled` → `True` (meaning: a fresh, structurally valid Private
  snapshot was obtained this cycle — not a persisted restart-reconciliation
  guarantee)
- `broker_snapshot_fresh` → `True`
- `position_count` → `private.open_positions_count`
- `active_order_count` → `private.active_orders_count`

`notification_path_ready`, `entries_today`, `daily_stop_clear`,
`monthly_stop_clear`, `consecutive_loss_stop_clear`, and `operator_halt_clear`
pass through from `base` unchanged. A caller composing this against Phase 1's
`_fail_closed_preflight` output would still see the cycle block on
`NOTIFICATION_PATH_NOT_READY` and `DAILY_ENTRY_LIMIT_REACHED` (from the
Phase-1 sentinel's `entries_today=1`) even with a fully clear, flat, real
account snapshot — that is intentional; those dimensions are not addressed by
this slice.

## Deferred scope (not implemented here)

- **Notification lane** (Pushover/SMTP send, readiness check): the existing
  `app/services/h11_v4_notification_binding_no_post.py` generic no-POST
  binding is a candidate to reuse for a future slice, but wiring it in is
  deliberately out of scope for this pass.
- **Daily/monthly/consecutive-loss-stop tracking**: requires persisted P&L /
  trade-history state that does not yet exist for the shadow controller.
- **Host/dead-man state, operator persistent HALT file wiring**: separate from
  the shadow ledger's own sticky-HALT (`V4UnattendedShadowStore.latch_halt`),
  which already exists and is unaffected by this module.
- **Runner CLI wiring**: this module is not called from
  `backend/scripts/h11_auto_v4_unattended_shadow_run.py`. Wiring it in — and
  deciding how a real credential pair reaches an unattended runner — is a
  separate, explicitly authorized future change with its own review.

## Structural exclusions

The module has no import, reference, or call to:

- A real Keychain reader (no `subprocess`, no `security find-generic-password`)
- Any G013-specific gated/preparation module
  (`h11_v4_gmo_readonly_preflight`, `h11_v4_gmo_actual_transport`,
  `h11_v4_gmo_actual_adapter`, `h11_v4_gmo_post_canary_reconciliation`)
- Broker write endpoints (`order`, `cancelOrders`, `closeOrder`, OCO)
- Pushover, SMTP, or any notification transport
- `app.h11_manual` (this module lives in `app.services`, the same bridge
  layer as the Phase 1 Public adapter, and does not import the manual-UI
  package)
