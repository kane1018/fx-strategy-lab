# Step 6G Dummy Signing Plan

Step 6G-DS adds a dummy signing check after the Step 6G internal wiring dry-run.
It is not real signing, not real transport, and not live execution permission.

## Background

- Step 6G-IW connected PB / EB / AD / RA / TC / ST with one fake/sanitized
  snapshot.
- The next minimum-risk step is to verify the signing input shape without
  credentials, signature values, header values, API calls, or HTTP POST.
- Real signing and real transport remain separate future Steps.

## Implemented Model

- New dummy signing model:
  `backend/app/live_verification/live_order_real_dummy_signing.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_dummy_signing.py`
- Minimal internal wiring integration:
  `backend/app/live_verification/live_order_real_step6g_internal_wiring.py`

## Dummy Signing Boundary

The dummy check accepts metadata only:

- `method=POST`
- `path=/v1/order`
- body contract ready flag
- stable serialization ready flag
- dummy timestamp/key/secret material labels
- algorithm label `HMAC-SHA256`
- header-name labels only

It does not use real credentials, read env, read `.env`, generate real
signatures, generate real header values, retain a dummy signature value, expose
raw request/response, or expose real IDs.

## Ready State

Ready means:

- `DUMMY_SIGNING_CHECK_PASSED_NO_VALUE_EXPOSED`
- `dummy_signing_ready=true`
- `dummy_signature_check_performed=true`
- `dummy_signature_check_passed=true`
- `signature_value_present=false`
- `credential_value_present=false`
- `header_values_present=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

Ready is not real signing permission and not POST permission.

## Blockers

The model blocks:

- method/path mismatch
- body contract or stable serialization not ready
- missing dummy labels
- real credential request
- env or `.env` access request
- real signature request
- signature/header/credential value exposure or storage
- raw request/response exposure
- unsupported algorithm
- HTTP POST, order endpoint, or `live_order_once` execution flags
- retry or loop flags

## Internal Wiring

Step 6G-IW now requires the dummy signing check to be ready. If dummy signing is
not ready, the internal wiring remains blocked. If dummy signature value flags
are present, internal wiring blocks as raw/secret exposure.

## Future Work

Future real signing must be a separate reviewed Step. Future real execution
still requires a new final confirmation, fresh final-confirmation preflight,
fresh POST-immediate preflight, one POST maximum, no retry, and sanitized
post-attempt reconciliation.
