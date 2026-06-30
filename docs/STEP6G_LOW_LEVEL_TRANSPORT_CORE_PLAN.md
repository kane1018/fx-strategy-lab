# Step 6G Low-Level Transport Core Plan

Step 6G-TC adds a low-level order transport core as a pure/fake model. It does
not execute API calls, HTTP POST, an order endpoint, `live_order_once`, or a
real order.

## Background

- Step 6G-LT concluded CASE 2.
- The existing `live_order_once.py` Step 4 entry should not be called directly
  from Step 6G.
- Step 4 approval phrase and Step 4 ledger `PREPARED` state must not be spoofed
  or forcibly converted.
- Low-level transport concepts can be extracted only when they stay independent
  of Step 4 approval and ledger state.

## Implemented Core

- New module:
  `backend/app/live_verification/live_order_real_order_transport_core.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_order_transport_core.py`
- The core covers:
  - order body allowlist for `symbol`, `side`, `size`, and `executionType`
  - deterministic stable JSON serialization for fake tests
  - method/path endpoint contract metadata only
  - redacted header-name contract only
  - fake/sanitized result classification
  - one-shot/no-retry contract checks
  - raw/secret/real ID exposure blockers

## Safety Boundary

Ready or classified results keep:

- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `retry_allowed=false`
- `loop_allowed=false`
- add/change/cancel/close disabled

This Step does not use real credentials, generate real signed values, expose
header values, store raw request/response data, or return real IDs.

## Fake Result Classification

The core accepts sanitized fake result inputs only and classifies them as:

- `TRANSPORT_SUCCESS_SANITIZED`
- `TRANSPORT_API_REJECTED_SANITIZED_NO_RETRY`
- `TRANSPORT_TIMEOUT_SANITIZED_NO_RETRY`
- `TRANSPORT_ERROR_SANITIZED_NO_RETRY`
- `TRANSPORT_RESULT_UNKNOWN_SANITIZED_NO_RETRY`

Unknown, timeout, and reject categories do not retry.

## Future Work

Future real signing and real transport implementation must be a separate Step.
Future real Step 6G execution still requires a new final confirmation, fresh
final-confirmation preflight, fresh POST-immediate preflight, and sanitized
post-attempt reconciliation only.
