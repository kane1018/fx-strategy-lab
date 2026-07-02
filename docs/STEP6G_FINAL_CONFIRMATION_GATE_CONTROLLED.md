# Step 6G Final Confirmation Gate Controlled

Step 6G-PC-OX-R-FINAL-CONFIRMATION-GATE adds a safe final confirmation gate
contract for the boundary after fresh preflight PASS.

This document describes the gate implementation only. This step does not obtain
the actual final confirmation. The next retry step must request a new explicit
current-turn user reply in the Codex session.

## Scope

Allowed in this gate:

- safe final confirmation gate label
- safe final confirmation gate status
- fresh preflight PASS prerequisite booleans
- final confirmation required boolean
- current-turn explicit user reply received boolean
- confirmation new / current-turn / one-time / non-reuse booleans
- previous-turn confirmation reuse blocker
- Step 4 approval phrase reuse blocker
- confirmation actual value stored / reported / logged false booleans
- POST / order / live_order_once / ledger / receipt false booleans
- safe blocked reason labels
- recommended next step label

Not allowed in this gate:

- HTTP POST
- order endpoint call
- `live_order_once`
- one-shot POST
- real order placement
- ledger update
- attempt counter persistence
- actual result receipt
- actual receipt handoff
- raw request display, save, or return
- raw response display, save, or return
- broker/API response actual value display, save, parse, or return
- credential value display, save, or return
- signature value display, save, or return
- headers value display, save, or return
- account ID, order ID, transaction ID, position ID, trade ID, or real ID display
- final confirmation phrase actual value display, save, log, or return
- Step 4 approval phrase actual value display, save, log, or return
- ledger state actual value display, save, log, or return
- Step 6G real funds retry

## Contract

The gate is implemented in:

- `backend/app/live_verification/live_order_real_final_confirmation_gate_controlled.py`

It accepts only safe booleans and labels. It does not accept a confirmation
phrase string and therefore cannot store, render, or log the phrase actual
value.

Default state:

- `fresh_preflight_passed=true`
- `fresh_preflight_current=true`
- `fresh_preflight_new=true`
- `fresh_preflight_reused=false`
- `fresh_preflight_stale=false`
- `final_confirmation_required=true`
- `final_confirmation_received=false`
- `current_turn_explicit_user_reply_received=false`
- `post_allowed_this_step=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `ledger_updated=false`
- `attempt_counter_persisted=false`
- `actual_receipt_handoff_executed=false`

Default status:

- `FINAL_CONFIRMATION_GATE_READY_FOR_REQUEST_NO_POST`

Confirmed status is possible only when the caller provides safe booleans showing
a new current-turn explicit user reply:

- `final_confirmation_received=true`
- `current_turn_explicit_user_reply_received=true`
- `confirmation_current_turn=true`
- `confirmation_new=true`
- `confirmation_one_time=true`
- `confirmation_reused=false`
- `previous_turn_confirmation_reused=false`
- `step4_approval_phrase_reused=false`
- `confirmation_actual_value_stored=false`
- `confirmation_actual_value_reported=false`
- `confirmation_actual_value_logged=false`

The confirmed status is:

- `FINAL_CONFIRMATION_GATE_CONFIRMED_NO_POST`

This still does not permit POST in the same step.

## Rejected Sources

The gate rejects:

- previous-turn confirmation reuse
- Step 4 approval phrase reuse
- this prompt being treated as final confirmation
- fresh preflight PASS report being treated as final confirmation
- any confirmation phrase actual value storage, report, or log attempt

## Fail-Closed Conditions

The gate fails closed for:

- missing fresh preflight PASS / current / new / non-reused prerequisite
- fresh preflight unknown / timeout / unavailable / stale / reused
- non-current-turn confirmation
- non-new confirmation
- non-one-time confirmation
- reused confirmation
- previous-turn confirmation reuse
- Step 4 approval phrase reuse
- confirmation actual value exposure attempt
- POST / order endpoint / `live_order_once`
- ledger update or attempt counter persistence
- actual result receipt or receipt handoff
- raw request / raw response / broker/API response exposure
- credential / signature / header value exposure
- real ID exposure

## Next Step

Because this step implemented the safe gate, it must not also obtain the actual
final confirmation in the same step.

Recommended next step:

```text
Step 6G-PC-OX-R-FINAL-CONFIRMATION-GATE-RETRY
```

That step may request a new current-turn explicit final confirmation and
validate it through this safe gate. It still must not execute HTTP POST, call
order endpoints, call `live_order_once`, update ledgers, persist attempt
counters, receive actual results, or hand off receipts.
