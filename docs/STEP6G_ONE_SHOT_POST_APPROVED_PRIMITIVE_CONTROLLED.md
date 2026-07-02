# Step 6G One-Shot POST Approved Primitive Controlled

Step 6G-PC-OX-R-ONE-SHOT-POST-APPROVED-PRIMITIVE-RESOLUTION-C implements the
approved primitive boundary that can feed the controlled real transport binding
in a later execution gate.

This step is boundary implementation only. It is not actual HTTP POST, not an
order endpoint call, and not `live_order_once` execution.

## Scope

Implemented in:

- `backend/app/live_verification/live_order_real_one_shot_post_approved_primitive_controlled.py`

The boundary exposes:

1. approved primitive availability safe summary
2. approved primitive construction guard
3. controlled callable interface
4. sanitized primitive outcome mapping
5. no-execution default/import/summary/construct path

The implementation does not import or call:

- `live_order_once`
- broker clients
- Private API clients
- HTTP clients
- env readers
- ledger writers
- receipt handoff code

## Safe Summary

The availability summary exposes safe labels, booleans, counts, categories, and
blocked reason labels only:

- `approved_primitive_available`
- `approved_primitive_status`
- `approved_primitive_label`
- `approved_primitive_default_no_execution=true`
- `approved_primitive_import_executes_post=false`
- `approved_primitive_construct_executes_post=false`
- `approved_primitive_summary_executes_post=false`
- `controlled_executor_required=true`
- `post_specific_confirmation_required=true`
- `one_post_max=true`
- `retry_allowed=false`
- `timeout_fail_closed=true`
- `ledger_update_this_step=false`
- `receipt_handoff_this_step=false`
- `raw_request_exposed=false`
- `raw_response_exposed=false`
- `broker_api_response_exposed=false`
- `credential_value_exposed=false`
- `signature_value_exposed=false`
- `headers_value_exposed=false`
- `real_id_exposed=false`

## Approved Primitive Contract

The boundary is constructed with a caller-supplied primitive:

```text
construct_live_order_real_one_shot_post_approved_primitive_controlled(
  primitive=...
)
```

Construction does not call the primitive. Importing the module, rendering the
summary, or constructing the boundary does not POST.

The primitive is acceptable only when the contract says:

- approved primitive source supplied
- controlled executor required
- POST-specific confirmation required
- one POST max
- retry disabled
- timeout fail-closed
- ledger and receipt paths separated
- no raw request/response exposure
- no broker/API response exposure
- no credential/signature/header value exposure
- no real/account/order/transaction ID exposure

If any contract flag is unsafe, the boundary fails closed and the controlled
callable returns a sanitized failed outcome without calling the primitive.

## Controlled Binding Compatibility

The controlled primitive is intended to be passed to:

```text
construct_live_order_real_one_shot_post_real_transport_binding_controlled(
  primitive=approved.controlled_primitive
)
```

The binding and executor still own the one-call boundary. Tests verify this
connection using fake/monkeypatch primitives only.

Timeout, failure, unknown, and unavailable outcomes fail closed. Unsafe fake
outcomes are sanitized so raw request/response, broker/API response, IDs,
credential values, signature values, headers values, ledger updates, and receipt
handoff flags do not propagate.

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
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-4
```

That step must first confirm the repository state and prerequisite gates, show
the sanitized executable order preview, then obtain a new POST-specific explicit
confirmation in the current Codex session. Only after those checks may it
consider one HTTP POST through the safe route, approved primitive boundary, and
controlled binding.

The next step must still keep these boundaries separate:

- HTTP POST and retry/repost
- HTTP POST and ledger update
- HTTP POST and attempt counter persistence
- HTTP POST and actual result receipt
- actual receipt handoff and any future order action
