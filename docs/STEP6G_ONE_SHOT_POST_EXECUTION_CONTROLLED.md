# Step 6G One-Shot POST Execution Controlled

Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-RUNTIME-C implements the safe
one-shot POST execution route for a later dedicated POST gate.

This step is route implementation only. It is not actual HTTP POST, not an
order endpoint call, and not `live_order_once` execution.

## Scope

Implemented in:

- `backend/app/live_verification/live_order_real_one_shot_post_execution_controlled.py`

The route has three safe layers:

1. executable sanitized order preview
2. POST-specific confirmation safe validator
3. one-shot controlled executor with injected transport

The implementation does not import or call:

- `live_order_once`
- broker clients
- Private API clients
- HTTP clients
- env readers
- ledger writers
- receipt handoff code

## Sanitized Preview

The preview exposes safe labels, booleans, and repo-defined order intent fields
only:

- `execution_step`
- `fresh_preflight_passed`
- `final_confirmation_received`
- `ready_gate_passed`
- `post_guard_ready`
- `one_post_max`
- `retry_allowed=false`
- `timeout_fail_closed=true`
- `actual_post_requires_post_specific_confirmation=true`
- `ledger_update_this_step=false`
- `receipt_handoff_this_step=false`
- `raw_exposure=false`
- `id_exposure=false`
- `credential_value_exposure=false`
- `symbol`
- `side`
- `order_type`
- `size`
- safe environment/risk labels

The preview fails closed when the safe order candidate is missing, ambiguous,
unsupported, Codex-inferred, or requires raw/ID/value exposure.

The preview does not expose:

- account ID
- order ID
- transaction ID
- raw payload
- raw endpoint
- broker/API response
- credential values
- signature values
- header values

## POST-Specific Confirmation

The route requires a new POST-specific confirmation in the later execution
gate. The existing final confirmation and ready gate confirmation cannot be
reused as POST permission.

Safe confirmation fields:

- `post_specific_confirmation_required=true`
- `post_specific_confirmation_received`
- `post_specific_confirmation_current_turn`
- `post_specific_confirmation_new`
- `post_specific_confirmation_one_time`
- `post_specific_confirmation_reused=false`
- `final_confirmation_reused_as_post_confirmation=false`
- `ready_gate_confirmation_reused_as_post_confirmation=false`
- `previous_turn_confirmation_reused=false`
- `step4_approval_phrase_reused=false`
- `post_confirmation_actual_value_stored=false`
- `post_confirmation_actual_value_reported=false`
- `post_confirmation_actual_value_logged=false`

Confirmation actual values are not stored, returned, logged, or rendered.

## Controlled Executor

The executor is available as an injected-transport route:

```text
execute_live_order_real_one_shot_post_execution_controlled(..., transport=...)
```

The executor calls the injected transport at most once only when all safe
conditions are already true:

- fresh preflight passed/current/new/non-reused
- final confirmation received/current-turn/new/one-time/non-reused
- one-shot POST ready gate passed
- sanitized preview available
- order ambiguity is false
- POST-specific confirmation validated
- one POST max
- retry disabled
- timeout fail-closed
- ledger update disabled for this step
- receipt handoff disabled for this step
- raw/ID/value exposure disabled

The executor does not retry on failure, timeout, unknown, or unavailable result.
It does not perform a second POST. It does not update ledgers, persist attempt
counters, receive actual receipts, or perform actual receipt handoff.

## Transport Boundary

The route accepts a transport callable. Step
6G-PC-OX-R-ONE-SHOT-POST-REAL-TRANSPORT-BINDING-C adds a controlled real
transport binding contract that can be injected into this route by a later
dedicated execution gate. The binding default/import/summary/construct paths do
not POST.

A later `ONE-SHOT-POST-EXECUTION-GATE-RETRY-2` may pass the controlled binding
only after a new POST-specific explicit confirmation and only if every gate is
still clean.

## Result Mapping

The result maps the injected transport outcome to safe summary fields only:

- `post_attempted`
- `http_post_executed`
- `post_execution_count`
- `second_post_attempted=false`
- `retry_attempted=false`
- `safe_post_execution_status`
- `safe_post_execution_label`
- `safe_result_category`
- `safe_reconciliation_status`
- `ledger_updated=false`
- `attempt_counter_persisted=false`
- `actual_receipt_handoff_executed=false`
- `raw_request_exposed=false`
- `raw_response_exposed=false`
- `broker_api_response_exposed=false`
- `credential_value_exposed=false`
- `signature_value_exposed=false`
- `headers_value_exposed=false`
- `real_id_exposed=false`

It does not expose raw request, raw response, broker/API response bodies,
account/order/transaction IDs, credential values, signature values, header
values, endpoint values, confirmation phrases, or ledger state values.

## What This Step Did Not Do

This implementation step did not:

- execute actual HTTP POST
- call an order endpoint
- call `live_order_once`
- obtain POST-specific confirmation
- rerun fresh preflight
- reacquire final confirmation
- update ledger state
- persist an attempt counter
- receive actual result receipts
- perform actual receipt handoff
- retry or repost
- read `.env` or `.env.example`
- display credentials, signatures, headers, raw data, IDs, or confirmation text

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-2
```

That step must first show the sanitized preview, then obtain a new
POST-specific explicit confirmation in the current Codex session. Only after
that may it consider one HTTP POST through the safe route.

The next step must still keep these boundaries separate:

- HTTP POST and retry/repost
- HTTP POST and ledger update
- HTTP POST and attempt counter persistence
- HTTP POST and actual result receipt
- actual receipt handoff and any future order action
