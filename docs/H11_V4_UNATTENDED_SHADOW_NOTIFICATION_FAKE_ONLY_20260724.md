# H-11 v4 Unattended Shadow Notification Decision Layer — Slice 2, Fake-only

Date: 2026-07-24

## Objective

Phase 3 slice 2: decide *whether* a shadow cycle's outcome is worth
notifying about, with dedup so a sticky HALT (which every subsequent cycle
re-reports) notifies exactly once rather than every cycle forever. This slice
does not send anything real: sending goes through the existing, generic,
already-reviewed `H11V4DisabledDualRouteNotifier`
(`backend/app/services/h11_v4_notification_binding_no_post.py`), whose default
(Refusing) transports remain structurally incapable of a real send. This
module is not wired into the shadow runner CLI.

## Why extend the existing notification enum instead of duplicating it

Phase 3 slice 1's review found that duplicating the Private-GET read/parse
shape (rather than reusing the gated precedent) created a real drift risk —
two independently-maintained copies of the same logic, one of which had
already silently regressed relative to the other. The notification binding
module (`H11V4NotificationEvent`, `H11V4PushoverRequest`,
`H11V4DisabledDualRouteNotifier`, the Fake/Refusing transports) is
considerably more machinery than the Private-GET read sequence, so
duplicating it a second time for shadow-specific events would repeat that
mistake at a larger scale.

Instead, this slice makes a **purely additive** change to the existing,
shared `H11V4NotificationEvent` enum: two new members,
`SHADOW_ACTIONABLE_OBSERVED` (non-critical) and `SHADOW_HALT_ENGAGED`
(critical — added to `CRITICAL_EVENTS`, since the shadow ledger's sticky HALT
has no clear/reset path and the operator genuinely needs to know). No
existing member, value, or `CRITICAL_EVENTS` entry changes. The consumers of
this module (`h11_v4_notification_actual_preparation.py`,
`v4_host_rehearsal.py`) and their full test suites (64 tests) were run before
and after the change to confirm nothing broke; there is no exhaustive
enum-count assertion anywhere that a purely additive change could trip.

## Decision contract

`decide_shadow_notification_event(*, report, previous_status)`:

- Returns `None` for a routine cycle (any status other than
  `SHADOW_HALTED` / `SHADOW_WOULD_ENTER_NON_AUTHORIZING`), and for a
  notify-worthy status that is unchanged from `previous_status` (dedup).
- Returns `H11V4NotificationEvent.SHADOW_HALT_ENGAGED` the first cycle
  `status` becomes `SHADOW_HALTED`.
- Returns `H11V4NotificationEvent.SHADOW_ACTIONABLE_OBSERVED` the first cycle
  `status` becomes `SHADOW_WOULD_ENTER_NON_AUTHORIZING`.
- `previous_status=None` (the very first cycle ever observed) is itself a
  transition — a pre-latched HALT observed on cycle 1 still notifies.

This is a pure function: no I/O, no state of its own. The caller (a future
runner integration) is responsible for supplying the correct
`previous_status`, e.g. the prior ledger row's status — that wiring is
explicitly deferred, matching every other real-capability boundary in this
track.

**Named foot-gun for the future runner-wiring change**: because this module
holds no state, nothing here prevents a careless future caller from always
passing `previous_status=None`. Since `None` never equals a real
`V4ShadowDecisionStatus`, doing so would make *every* cycle look like a fresh
transition — a sticky `SHADOW_HALTED` would then notify on every single
cycle forever, exactly the failure mode dedup exists to prevent. The
runner-wiring change must thread `previous_status` from the persistent
ledger's actual prior row (not a hardcoded or default value), and should
include a test asserting that.

`notify_shadow_cycle_once(*, report, previous_status, notifier)` composes the
decision with exactly one `notifier.notify_once(event)` call when notify-worthy,
and requires `notifier` to be the exact reviewed `H11V4DisabledDualRouteNotifier`
class (`type(notifier) is not H11V4DisabledDualRouteNotifier` is rejected) —
its own constructor already refuses any transport whose `fake_only` is not
literally `True`, so this function inherits that guarantee rather than
re-implementing it.

## Structural exclusions

The module has no import, reference, or call to:

- Any real Pushover/SMTP transport, `httpx`, `smtplib`
- Private API, Keychain, credential, or any G013-gated preparation module
- The shadow runner CLI (not wired in)
- `app.h11_manual`

## Deferred scope

- Runner CLI wiring (deciding how `previous_status` is sourced from the
  persistent ledger in a live run) — separate future change.
- A real Pushover/SMTP transport — separate future change requiring its own
  explicit authorization, exactly like Phase 3 slice 1's Private-GET client.
- Daily/monthly/consecutive-loss-stop tracking, host/dead-man state,
  operator persistent HALT — out of scope for this slice, as for slice 1.
