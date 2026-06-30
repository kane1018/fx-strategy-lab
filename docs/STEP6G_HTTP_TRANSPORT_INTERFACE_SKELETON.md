# Step 6G HTTP Transport Interface Skeleton

Step 6G-HT adds an HTTP transport interface skeleton after the Step 6G dummy
signing check. It is interface-only. It does not include an HTTP client, execute
API calls, execute HTTP POST, call an order endpoint, call `live_order_once`, or
place a real order.

## Background

- Step 6G-DS added a dummy signing check with no real credentials, no real
  signature values, no header values, no API, and no POST.
- Step 6G-IW now requires dummy signing ready / dummy check passed before the
  internal fake/sanitized chain can be ready.
- The next safe boundary is an interface contract for a future real transport,
  still without real transport implementation.

## Implemented Interface

- New interface skeleton:
  `backend/app/live_verification/live_order_real_http_transport_interface.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_http_transport_interface.py`
- Minimal internal wiring integration:
  `backend/app/live_verification/live_order_real_step6g_internal_wiring.py`

The interface accepts metadata only:

- `interface_mode=INTERFACE_ONLY`
- `method=POST`
- `path=/v1/order`
- endpoint/body/serialization/signing/dummy-signing/private-transport readiness
- one-shot/no-retry attempt state
- explicit false flags for HTTP client, POST capability, order endpoint,
  `live_order_once`, credentials, signatures, header values, raw data, and real IDs

## Ready State

Ready means:

- `HTTP_TRANSPORT_INTERFACE_READY_NO_API_NO_POST`
- `interface_ready=true`
- `http_client_present=false`
- `can_execute_http_post=false`
- `can_call_order_endpoint=false`
- `can_call_live_order_once=false`
- `credential_values_provided=false`
- `signature_value_generated=false`
- `header_values_present=false`
- `raw_request_present=false`
- `raw_response_present=false`
- `real_ids_present=false`
- `post_allowed_this_step=false`
- `post_executed=false`

Ready is not real transport permission and not POST permission.

## Blockers

The model blocks:

- non-`INTERFACE_ONLY` mode
- method/path mismatch
- prerequisite readiness mismatch
- retry, loop, second attempt, add/change/cancel/close flags
- real transport request
- HTTP client presence
- HTTP POST capability
- order endpoint capability
- `live_order_once` capability
- credential, signature, header value, raw request, raw response, or real ID exposure

## Internal Wiring

Step 6G-IW now requires the HTTP transport interface to be ready. If the
interface is not ready, or if an HTTP client / POST / order endpoint /
`live_order_once` capability flag is present, internal wiring remains blocked.

## Safety Boundary

This Step does not use real credentials, generate real signatures, generate
real header values, read env, read `.env`, display or save raw request/response
data, expose real IDs, mutate ledger state, or spoof Step 4 approval.

Future real transport must be a separate reviewed Step. Future real execution
still requires a new final confirmation, fresh final-confirmation preflight,
fresh POST-immediate preflight, one POST maximum, no retry, and sanitized
post-attempt reconciliation.
