# Step 3 Live Order Preflight Review

## 1. Purpose

Step 3 is an independent final audit before any Step 4 live-order task.

This step checks whether the project is ready to prepare a Step 4 prompt. It does
not authorize a live order by itself.

Step 3 explicitly does not:

- send HTTP POST requests
- place a live order
- run real-money verification
- add a broker
- add an OrderRequest
- add a public backend API
- change frontend behavior

## 2. Step 1 / Step 2 Completion State

Step 1 completed the local-only signed bundle and mock signed transport path:

```text
ActualOrderRequestBody
-> ActualHeadersSignatureBundle
-> MockSignedOrderTransportResult
```

Step 2 completed the disabled order submission skeleton and mock submission path:

```text
ActualHeadersSignatureBundle
-> OrderSubmissionSafetyDecision
-> DisabledOrderSubmissionSkeletonResult
-> MockOrderSubmissionSkeletonResult
```

Both steps remain mock-only / no-network for order submission. HTTP POST and live
orders are still not implemented.

## 3. Step 3 Audit Items

Step 3 checks a sanitized preflight snapshot with these categories:

- credential presence only: `api_key_present`, `api_secret_present`
- read-only precheck success flags
- `open_positions_count` and `active_orders_count`
- known previous result state
- Step 2 skeleton and mock submission status
- tests / ruff / git clean status
- market window, maintenance, and important-event flags
- first-live-order-only constraints
- attempt counters and max daily attempts
- retry / loop / kill-switch / safety violation flags
- HTTP POST and real-order-attempt flags

The audit returns one of:

- `READY_FOR_STEP4_PROMPT`: Step 4 prompt preparation is allowed, but Step 4 still
  requires separate explicit user approval.
- `NO_GO`: Step 4 must not proceed. Reasons are listed in `no_go_reasons`.

Step 3 always keeps `live_order_allowed_now=false`.

## 4. Read-Only Checks

If and only if the existing read-only client / existing procedure is available
and credentials are present, Step 3 may verify:

- `GET /private/v1/account/assets`: success / failure only
- `GET /private/v1/openPositions`: count only
- `GET /private/v1/activeOrders`: count only

Required preflight state:

- account/assets check succeeds
- openPositions check succeeds
- activeOrders check succeeds
- `open_positions_count=0`
- `active_orders_count=0`

If credentials are missing, connection fails, or only raw responses can be
obtained, Step 3 must return `NO_GO`.

## 5. Output Policy

Allowed output:

- `GMO_FX_API_KEY: set / missing`
- `GMO_FX_API_SECRET: set / missing`
- `readonly_assets_check_passed: true / false`
- `open_positions_count`
- `active_orders_count`
- sanitized Go / No-Go reasons

Forbidden output:

- API key value
- API secret value
- signature value
- header values
- raw request
- raw response
- account balance details
- open position details
- active order details
- request URL
- response headers

## 6. Step 4 Conditions

Step 4 may only be prepared if Step 3 returns `READY_FOR_STEP4_PROMPT`.

Step 4 still requires separate explicit user approval. The Step 3 preflight
result is not a substitute for that approval.

The Step 4 approval must include:

- `USD_JPY`
- `100` units
- one attempt only
- manual execution only
- understanding that real funds are involved
- no retry, loop, or additional order after the one attempt

## 7. First Live Order Constraints

The first live-order preflight must enforce:

- `symbol=USD_JPY`
- `units=100`
- `max_daily_attempts=1`
- `session_attempt_count=0`
- `daily_attempt_count=0`
- `initial_live_order_only=true`
- `retry_enabled=false`
- `loop_enabled=false`
- `result_unknown=false`
- `manual_approval_required=true`
- `manual_approval_present_for_execution=false` during Step 3

`manual_approval_present_for_execution=true` is invalid in Step 3 because this
step must not include the live-order execution approval.

## 8. Stop Conditions

Step 3 must return `NO_GO` if any of the following are true:

- API key presence is missing
- API secret presence is missing
- read-only account/assets check fails
- read-only openPositions check fails
- read-only activeOrders check fails
- existing open positions are present
- active orders are present
- previous result is unknown
- result is unknown
- Step 2 skeleton did not pass
- mock submission did not pass
- tests failed
- ruff failed
- git is dirty
- market window is not allowed
- maintenance is active
- important event window is active
- not first-live-order-only
- manual approval is not required
- manual approval for execution is already present in Step 3
- `max_daily_attempts != 1`
- `session_attempt_count != 0`
- `daily_attempt_count != 0`
- retry is enabled
- loop is enabled
- kill switch is active
- a safety violation is detected
- HTTP POST is enabled
- a real order was attempted
- a count is negative
- a count is passed as bool
- a flag is non-bool

Multiple violations must remain visible as multiple `no_go_reasons`.

## 9. Time Rules

Step 3 requires `market_window_allowed=true`,
`maintenance_active=false`, and `important_event_window_active=false`.

If any of these cannot be verified safely, the conservative result is `NO_GO`.

## 10. Current Step 3 Execution Result

This run was executed in a Codex environment where credential presence was:

```text
GMO_FX_API_KEY: missing
GMO_FX_API_SECRET: missing
```

Because required credential presence was missing, the existing read-only
connection procedure was not executed.

Sanitized result:

```text
readonly_assets_check_passed: false
open_positions_count: not verified
active_orders_count: not verified
raw_response_saved: false
```

Step 3 decision for this run:

```text
NO_GO
```

Reason:

```text
api_key_present
api_secret_present
readonly checks not executed
```

Step 4 must not proceed from this run.

## 11. Implementation Notes

Step 3 adds a local-only model:

- `LiveOrderPreflightSnapshot`
- `LiveOrderPreflightDecision`
- `evaluate_live_order_preflight`

This model stores only sanitized flags and counts. It does not store raw account
data, credentials, headers, signatures, requests, responses, URLs, or HTTP client
objects.

## 12. Still Forbidden

Step 3 still forbids:

- HTTP POST
- live order
- real-money verification
- Private API write requests
- order modification / cancellation / close endpoints
- retry order
- loop order
- broker implementation
- OrderRequest implementation
- real order API client implementation
- frontend execution UI
- public backend API additions
