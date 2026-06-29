# Step 6G Real Adapter Contract

Step 6G-RA adds a Step 6G real adapter contract model with stub transport only.
It does not execute API calls, HTTP POST, an order endpoint, `live_order_once`,
or a real order.

## Background

- Step 6G-RT concluded CASE 2.
- The existing `live_order_once.py` Step 4 entry should not be called directly
  from Step 6G.
- Step 4 approval phrase and Step 4 ledger `PREPARED` state must not be spoofed
  or forcibly converted.
- Low-level POST components may be extracted in a future reviewed Step, but this
  Step does not implement or call them.

## Implemented Contract

- New module:
  `backend/app/live_verification/live_order_real_step6g_real_adapter.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_step6g_real_adapter.py`
- The contract accepts Step 6G-PB route bridge evidence, Step 6G-EB fake runtime
  evidence, and Step 6G-AD controlled adapter evidence.
- Only `STUB_ONLY` transport is allowed in this Step.
- Real transport is blocked.

## Stub Transport Boundary

Stub result categories are:

- `STUB_REAL_ADAPTER_ACCEPTED_NO_API_NO_POST`
- `STUB_REAL_ADAPTER_REJECTED_NO_RETRY_NO_API_NO_POST`
- `STUB_REAL_ADAPTER_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST`
- `STUB_REAL_ADAPTER_TIMEOUT_NO_RETRY_NO_API_NO_POST`

These are contract-test outcomes only. They are not real POST results.

## Safety Defaults

Ready or stub-completed results keep:

- `allowed_for_live=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `real_http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`

The model blocks:

- real transport
- HTTP POST-capable transport
- order endpoint-capable transport
- `live_order_once`-capable transport
- broker / Private API / HTTP client imports
- retry / loop
- add / change / cancel / close
- second or later attempt
- raw request / raw response / headers / signature / credential exposure
- real ID exposure
- Step 4 approval phrase spoofing
- Step 4 ledger state mutation

## Future Work

Future real execution requires a separate Step with:

- a new final confirmation
- fresh final-confirmation preflight
- fresh POST-immediate preflight
- reviewed real transport implementation
- no retry on reject, timeout, or unknown result
- sanitized reconciliation only after any real POST attempt

Real transport implementation is explicitly out of scope for Step 6G-RA.
