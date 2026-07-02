# Step 6G One-Shot POST Real Transport Binding Controlled

Step 6G-PC-OX-R-ONE-SHOT-POST-REAL-TRANSPORT-BINDING-C implements the
controlled real transport binding contract for the safe one-shot POST execution
route.

This step is binding implementation only. It is not actual HTTP POST, not an
order endpoint call, and not `live_order_once` execution.

## Scope

Implemented in:

- `backend/app/live_verification/live_order_real_one_shot_post_real_transport_binding_controlled.py`

The binding exposes:

1. binding availability safe summary
2. construction guard
3. controlled transport callable wrapper
4. sanitized transport outcome mapping
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

The availability summary exposes safe labels, booleans, counts, and blocked
reason labels only:

- `real_transport_binding_available`
- `real_transport_binding_label`
- `real_transport_binding_status`
- `binding_default_no_execution=true`
- `binding_import_executes_post=false`
- `binding_construct_executes_post=false`
- `binding_summary_executes_post=false`
- `controlled_executor_required=true`
- `post_specific_confirmation_required=true`
- `credential_presence_checked=false`
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

## Binding Contract

The binding is constructed with a caller-supplied primitive:

```text
construct_live_order_real_one_shot_post_real_transport_binding_controlled(
  primitive=...
)
```

Construction does not call the primitive. Importing the module, rendering the
summary, or constructing the binding does not POST.

After Step 6G-PC-OX-R-ONE-SHOT-POST-APPROVED-PRIMITIVE-ACTUAL-SOURCE-SUPPLY-C,
the caller-supplied primitive should come through the approved primitive actual
source boundary, approved primitive source boundary, and approved primitive
boundary:

```text
construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
  actual_source=...
)
```

```text
construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
  source=actual_source_boundary.approved_primitive_actual_source
)
```

```text
construct_live_order_real_one_shot_post_approved_primitive_controlled(
  primitive=source_boundary.approved_primitive_source
)
```

Those boundaries also do not call the supplied actual source, source, or
primitive at import, summary, or construction time. They provide no-execution
availability summaries and sanitized callables that can be passed into this
binding.

The primitive is acceptable only when the contract says:

- approved primitive supplied
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

If any contract flag is unsafe, the binding fails closed and the constructed
callable returns a sanitized failed outcome without calling the primitive.

## Controlled Callable

The callable is intended to be passed to:

```text
execute_live_order_real_one_shot_post_execution_controlled(..., transport=...)
```

The controlled executor still owns the one-call boundary. Tests verify that the
binding composes with the executor using fake/monkeypatch primitives only.

The wrapper maps primitive outcomes to safe transport results and sanitizes
unsafe primitive results. Timeout, failure, unknown, and unavailable outcomes
fail closed. No retry and no second POST are attempted.

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
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-6
```

That step must first confirm the repository state and prerequisite gates, show
the sanitized executable order preview, then obtain a new POST-specific explicit
confirmation in the current Codex session. Previous POST-specific confirmation
text is not reusable. Only after those checks may it consider one HTTP POST
through the safe route, approved actual source boundary, approved primitive
source boundary, approved primitive boundary, and controlled binding.

The next step must still keep these boundaries separate:

- HTTP POST and retry/repost
- HTTP POST and ledger update
- HTTP POST and attempt counter persistence
- HTTP POST and actual result receipt
- actual receipt handoff and any future order action
