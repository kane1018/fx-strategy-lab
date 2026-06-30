# Step 6G Real Signing / Transport Contract

Step 6G-ST adds contract-only models for future real signing and private order
transport. It does not execute API calls, HTTP POST, an order endpoint,
`live_order_once`, or a real order.

## Background

- Step 6G-SR concluded CASE 2.
- The existing `live_order_once.py` Step 4 entry must not be called directly
  from Step 6G.
- Step 4 approval phrase and Step 4 ledger state must not be spoofed or
  forcibly converted for Step 6G.
- Signing, header, and transport-classification concepts may be reused only as
  Step 4-independent contract modules.

## Implemented Contracts

- New signing contract:
  `backend/app/live_verification/live_order_real_signing_contract.py`
- New private order transport contract:
  `backend/app/live_verification/live_order_real_private_order_transport.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_signing_contract.py`
  and
  `backend/app/tests/test_live_verification_live_order_real_private_order_transport.py`

## Signing Boundary

The signing contract handles metadata only:

- method/path contract
- stable body contract readiness
- timestamp required flag, without a generated timestamp value in this Step
- credential presence required flag, without credential values in this Step
- non-secret signature algorithm label
- allowed header-name labels only
- redacted header contract

It does not use credential values, generate real signatures, generate real
headers, read env, read `.env`, display or save header values, or persist
serialized body text.

## Transport Boundary

The private order transport contract handles contract-only prerequisites and
sanitized result categories:

- signing contract ready
- redacted header contract ready
- order body allowlist passed
- stable serialization ready
- endpoint/method contract ready
- one-post/no-retry contract
- sanitized success / rejected / timeout / error / unknown categories

Unknown, timeout, and rejected categories do not retry. The transport contract
does not hold an HTTP client, execute HTTP POST, call the order endpoint, call
`live_order_once`, retain raw request/response data, or expose real IDs.

## Safety Boundary

Ready or classified results keep:

- `credential_values_provided=false`
- `signature_value_generated=false`
- `header_values_redacted=true`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `retry_allowed=false`
- `loop_allowed=false`

## Future Work

Future real signing and real transport must be separate Steps. A future real
Step 6G execution still requires a new final confirmation, fresh
final-confirmation preflight, fresh POST-immediate preflight, and sanitized
post-attempt reconciliation only.
