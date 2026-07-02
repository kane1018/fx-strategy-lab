# Step 6G One-Shot POST Ready Gate Controlled

Step 6G-PC-OX-R-ONE-SHOT-POST-READY-GATE adds a safe final ready gate before a
later real one-shot POST execution step.

This gate is not HTTP POST, not an order endpoint call, and not `live_order_once`
execution. It only combines prior safe summaries and contract readiness into a
safe go/no-go label for planning the next dedicated POST execution step.

## Scope

Allowed in this gate:

- fresh preflight PASS prerequisite booleans
- final confirmation received / current-turn / new / one-time / non-reuse
  booleans
- POST guard readiness booleans
- one POST max / no retry / timeout fail-closed booleans
- final readiness readiness boolean
- final exec stack readiness boolean
- sanitized result contract readiness boolean
- ledger update after-POST-only boolean
- actual receipt handoff after-POST-only boolean
- safe one-shot POST ready gate label and status
- safe blocked reason labels
- recommended next step label

Not allowed in this gate:

- HTTP POST
- order endpoint call
- `live_order_once`
- one-shot POST execution
- real order placement
- fresh preflight rerun
- final confirmation reacquisition
- ledger update
- attempt counter persistence
- actual result receipt
- actual receipt handoff
- raw request display, save, or return
- raw response display, save, or return
- broker/API response actual value display, parse, save, or return
- credential value display, save, or return
- signature value display, save, or return
- headers value display, save, or return
- account ID, order ID, transaction ID, position ID, trade ID, or real ID display
- confirmation phrase actual value display, save, log, or return
- ledger state actual value display, save, log, or return
- Step 6G real funds retry

## Contract

The gate is implemented in:

- `backend/app/live_verification/live_order_real_one_shot_post_ready_gate_controlled.py`

Default passing prerequisites:

- `fresh_preflight_passed=true`
- `fresh_preflight_current=true`
- `fresh_preflight_new=true`
- `fresh_preflight_reused=false`
- `fresh_preflight_stale=false`
- `final_confirmation_received=true`
- `confirmation_current_turn=true`
- `confirmation_new=true`
- `confirmation_one_time=true`
- `confirmation_reused=false`
- `previous_turn_confirmation_reused=false`
- `step4_approval_phrase_reused=false`
- `post_guard_ready=true`
- `one_post_max=true`
- `retry_allowed=false`
- `timeout_fail_closed=true`
- `final_readiness_ready=true`
- `final_exec_stack_ready=true`
- `sanitized_result_contract_ready=true`
- `ledger_update_required_after_post_only=true`
- `actual_receipt_handoff_required_after_post_only=true`

Passing status:

- `ONE_SHOT_POST_READY_GATE_PASSED_NO_POST`

Passing result still fixes these fields to false:

- `actual_post_permitted_now=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `ledger_updated=false`
- `attempt_counter_persisted=false`
- `actual_receipt_handoff_executed=false`

## Meaning of PASS

`ready_gate_passed=true` means only:

- a later dedicated one-shot POST execution step may be planned

It does not mean:

- POST permission in this step
- order endpoint permission
- `live_order_once` permission
- ledger update permission
- actual receipt handoff permission
- retry or repost permission
- Step 6G real funds retry permission

The next step must obtain a new explicit real-POST-specific confirmation before
any POST execution is considered.

## Fail-Closed Conditions

The gate fails closed for:

- missing fresh preflight PASS / current / new / non-reused prerequisite
- fresh preflight unknown / failed / timeout / unavailable / stale / reused
- missing final confirmation current-turn / new / one-time prerequisite
- reused final confirmation
- previous-turn confirmation reuse
- Step 4 approval phrase reuse
- confirmation actual value storage, report, or log attempt
- POST guard not ready
- one POST max missing
- retry allowed
- timeout fail-closed missing
- final readiness not ready
- final exec stack not ready
- sanitized result contract not ready
- ledger update not after-POST-only
- actual receipt handoff not after-POST-only
- POST / order endpoint / `live_order_once`
- ledger update or attempt counter persistence
- actual result receipt or receipt handoff
- raw request / raw response / broker/API response exposure
- credential / signature / header value exposure
- real/account/order/transaction ID exposure

## Verification

The implementation is covered by:

- `backend/app/tests/test_live_verification_live_order_real_one_shot_post_ready_gate_controlled.py`
- `backend/app/tests/test_live_verification_no_order_imports.py`

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE
```

That step must be a dedicated POST execution step. It must not start with POST.
It must first obtain a new real-POST-specific explicit confirmation and must
still keep HTTP POST separated from retry/repost, ledger update, actual result
receipt, and actual receipt handoff.
