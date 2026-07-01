# Step 6G POST Guard Controlled

Step 6G-PC-OX-R-POST-GUARD-C adds a controlled POST guard boundary before any
future real POST step.

This step is not an API call, not HTTP POST, not an order endpoint call, and not
`live_order_once` execution. It only converts the controlled transport result
into safe POST guard labels, safe statuses, and booleans.

## Scope

Allowed in this step:

- `POST_GUARD_CONTROLLED_IMPLEMENTATION_ONLY`
- `POST_GUARD_READY_NO_POST`
- fixed safe POST guard label
- `post_guard_ready` safe boolean
- one POST max enforced safe boolean
- no retry enforced safe boolean
- timeout fail-closed enforced safe boolean
- fresh preflight required safe boolean
- final confirmation required safe boolean
- sanitized result required safe boolean
- safe blocked reason labels
- recommended next step label

Not allowed in this step:

- API call
- HTTP POST
- order endpoint call
- `live_order_once`
- raw request generation, display, save, or return
- raw response receipt, display, save, or return
- credential value display, save, or return
- signature value display, save, or return
- headers value display, save, or return
- endpoint actual value display, save, or return
- real ID, account ID, or order ID display, save, or return
- confirmation phrase actual value display, save, or return
- fresh preflight detail actual value display, save, or return
- ledger state actual value display, save, or return
- fresh preflight execution
- final confirmation execution
- actual checker execution
- actual result receipt or handoff
- Step 6G real funds retry

## Contract

The POST guard input accepts only safe transport readiness data:

- safe transport label
- safe transport status
- transport controlled ready boolean
- safe guard booleans and blocked reason controls

It does not accept credential values, signature values, headers values, raw
requests, raw responses, endpoint actual values, IDs, confirmation phrase actual
values, preflight detail actual values, or ledger state actual values.

The result is limited to:

- `safe_post_guard_label`
- `safe_post_guard_status`
- `post_guard_ready`
- `one_post_max_enforced`
- `no_retry_enforced`
- `timeout_fail_closed_enforced`
- `fresh_preflight_required`
- `final_confirmation_required`
- `sanitized_result_required`
- safe blocked reason labels
- `api_call_allowed=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`

## Meaning of Ready

`post_guard_ready=true` means only that the POST guard contract is in a safe
ready state for a later review step.

It does not mean:

- POST permission
- API permission
- order endpoint permission
- `live_order_once` permission
- fresh preflight completed
- final confirmation completed
- actual checker execution completed
- actual receipt handoff completed
- real order permission
- Step 6G real funds retry permission

## Guard Rules

The guard fixes these future POST requirements without executing POST:

- max POST attempts allowed is one
- second POST attempts are blocked
- multiple POST attempts are blocked
- retry after failure is blocked
- retry after timeout is blocked
- retry after unknown is blocked
- unknown / failed / unavailable / timeout fail closed
- rejected / stale / previous-turn / reused fail closed
- fresh preflight is required in a later step
- final confirmation is required in a later step
- sanitized result handling is required in a later step
- Step 4 approval phrase reuse is blocked
- ledger state reuse is blocked

Persistent POST attempt counters and ledger updates are not implemented in this
step. If they become necessary, they must be handled in a separate step before
any POST execution.

## Internal Wiring

Step 6G internal wiring includes `post_guard_controlled_ready` after
`transport_controlled_ready` and before private transport / HTTP interface gates.

The internal wiring fails closed for:

- missing or not-ready transport prerequisite
- unknown / failed / unavailable / timeout
- rejected / stale / previous-turn / reused
- retry attempted
- second POST attempted
- multiple POST attempts attempted
- API attempted
- POST attempted
- order endpoint called
- `live_order_once` called
- raw request or raw response exposure attempted
- credential / signature / headers value exposure attempted
- endpoint actual value or real ID exposure attempted
- confirmation phrase or ledger state exposure attempted
- fresh preflight attempted
- final confirmation attempted
- actual checker execution attempted
- actual receipt or handoff attempted

Even when the guard is ready, internal wiring keeps:

- `api_call_allowed=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `fresh_preflight_executed=false`
- `final_confirmation_received=false`

## Verification

The implementation is covered by:

- `backend/app/tests/test_live_verification_live_order_real_post_guard_controlled.py`
- `backend/app/tests/test_live_verification_live_order_real_step6g_internal_wiring.py`
- `backend/app/tests/test_live_verification_no_order_imports.py`

The no-order guard checks that the controlled POST guard module imports no HTTP
client, no private API, no broker module, no env loader, no crypto library, and
no `live_order_once`.

## Next Step

Recommended next step:

`Step 6G-PC-OX-R-POST-GUARD-V: one POST max / no retry / timeout fail-closed guard boundary review / no API call / no POST / no code change`

The next step is review-only. It must not call APIs, execute POST, call order
endpoints, call `live_order_once`, run fresh preflight, run final confirmation,
update ledgers, or retry Step 6G real funds.
