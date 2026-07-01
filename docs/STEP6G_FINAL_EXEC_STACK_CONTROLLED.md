# Step 6G Final Exec Stack Controlled Contract

Step 6G-PC-OX-R-FINAL-EXEC-STACK-C adds a dry-run only one-shot execution
stack before any future live POST. This is an implementation step, but it is
not a live execution step.

This step does not call APIs, execute HTTP POST, call order endpoints, call
`live_order_once`, use real transport, perform network I/O, run fresh
preflight, obtain final confirmation, update ledgers, persist attempt counters,
receive actual results, hand off receipts, or retry real-money Step 6G.

## Scope

Allowed in this step:

- `FINAL_EXEC_STACK_DRY_RUN_ONLY`
- `FINAL_EXEC_STACK_READY_DRY_RUN_ONLY`
- fixed safe dry-run stack label
- dry-run stack ready safe boolean
- fake/no-network transport flags
- dry-run one-shot decision label
- dry-run sanitized result category
- dry-run reconciliation preview label
- dry-run receipt handoff preview label
- dry-run ledger / attempt counter preview label
- safe blocked reason labels
- recommended next step label

Not allowed in this step:

- API call
- HTTP POST
- order endpoint call
- `live_order_once`
- real transport
- network I/O
- fresh preflight execution
- final confirmation execution or confirmation obtainment
- ledger update
- attempt counter persistence
- actual result receipt
- actual receipt handoff
- raw request generation, display, save, or return
- raw response receipt, display, save, or return
- broker/API response actual value display, save, parse, or return
- request body or response body display, save, or return
- endpoint actual value display, save, or return
- account ID, order ID, transaction ID, position ID, trade ID, or real ID
  display, save, or return
- credential value display, save, or return
- signature value display, save, or return
- headers value display, save, or return
- confirmation phrase actual value display, save, or return
- Step 4 approval phrase actual value display, save, or return
- ledger state actual value display, save, or return
- approval command actual value display, save, or return
- Step 6G real funds retry

## Contract

The final exec stack input accepts only safe final readiness, POST guard, and
sanitized result readiness data:

- safe final readiness label and status
- final readiness controlled ready boolean
- safe POST guard label and status
- POST guard controlled ready boolean
- safe POST result label and status
- safe reconciliation label and status
- sanitized result ready boolean
- reconciliation ready boolean
- dry-run stack safe booleans and blocked reason controls

It does not accept credential values, signature values, headers values, raw
requests, raw responses, broker/API response values, endpoint actual values,
IDs, confirmation phrase actual values, Step 4 approval phrase actual values,
ledger state actual values, or approval command actual values.

The result is limited to:

- `safe_dry_run_stack_label`
- `safe_dry_run_stack_status`
- `dry_run_stack_ready`
- `dry_run_mode=true`
- `fake_transport_used=true`
- `no_network_transport_used=true`
- `network_transport_used=false`
- `real_transport_used=false`
- `api_call_allowed=false`
- `api_call_executed=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `fresh_preflight_executed=false`
- `final_confirmation_received=false`
- `ledger_update_allowed=false`
- `ledger_updated=false`
- `attempt_counter_persistence_allowed=false`
- `attempt_counter_persisted=false`
- `actual_result_receipt_received=false`
- `actual_receipt_handoff_executed=false`
- `one_shot_post_allowed=false`
- safe dry-run preview labels
- safe blocked reason labels

## Meaning of Ready

`dry_run_stack_ready=true` means only that the dry-run execution stack contract
is ready for a later boundary review step.

It does not mean:

- API permission
- POST permission
- order endpoint permission
- `live_order_once` permission
- fresh preflight completed
- final confirmation completed
- ledger updated
- attempt counter persisted
- actual result receipt completed
- actual receipt handoff completed
- real order permission
- Step 6G real funds retry permission

`one_shot_post_allowed` remains `false`.

## Dry-Run Path

The dry-run path models the future flow only with safe labels and booleans:

```text
final readiness safe result
-> dry-run one-shot decision
-> fake/no-network transport
-> dry-run sanitized result
-> dry-run reconciliation preview
-> dry-run receipt handoff preview
-> dry-run ledger / attempt counter preview
-> safe summary output
```

The fake/no-network path is fixed as:

- `fake_transport_used=true`
- `no_network_transport_used=true`
- `network_transport_used=false`
- `real_transport_used=false`
- `raw_request_generated=false`
- `raw_response_received=false`
- `broker_response_received=false`
- `api_response_received=false`

## Runbook

Dry-run confirms:

- final readiness, POST guard, and sanitized result contracts can be connected
- one-shot decision remains blocked for live POST
- fake/no-network transport is the only transport label used
- sanitized result / reconciliation / receipt / ledger previews return safe
  labels only
- retry and multiple POST permissions remain absent
- ready states do not become POST permission

Dry-run does not confirm:

- live broker connectivity
- market state
- fresh preflight result
- final confirmation
- real POST payload or broker receipt
- ledger write behavior
- actual receipt handoff

Dry-run must not be used as a shortcut into live POST. The next step after this
implementation is a review-only boundary check. Fresh preflight execution, final
confirmation, and one-shot POST must remain separate later steps; fresh
preflight execution and HTTP POST must not be combined, final confirmation
execution and HTTP POST must not be combined, and ONE-SHOT-GATE and actual POST
must not be combined.

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-FINAL-EXEC-STACK-V:
dry-run one-shot execution stack boundary review / no API call / no POST / no code change
```

Even in the next step, API call, POST, order endpoint, `live_order_once`, fresh
preflight execution, final confirmation execution, ledger update, attempt
counter persistence, actual result receipt, actual receipt handoff, raw
request/response display, broker/API response display, credential/signature/
headers value display, real ID display, and real-money Step 6G retry remain
forbidden.
