# Step 6G One-Shot POST Approved Primitive Source Controlled

Step 6G-PC-OX-R-ONE-SHOT-POST-APPROVED-PRIMITIVE-SOURCE-SUPPLY-C implements the
approved primitive source supply boundary that can feed the approved primitive
boundary and controlled real transport binding in a later execution gate.

This step is source-boundary implementation only. It is not actual HTTP POST,
not an order endpoint call, not `live_order_once` execution, and not a
POST-specific confirmation step.

## Scope

Implemented in:

- `backend/app/live_verification/live_order_real_one_shot_post_approved_primitive_source_controlled.py`

The boundary exposes:

1. approved primitive source availability safe summary
2. approved primitive source construction guard
3. source-to-approved-primitive adapter
4. controlled binding and executor compatibility surface
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

- `approved_primitive_source_available`
- `approved_primitive_source_status`
- `approved_primitive_source_label`
- `approved_primitive_source_default_no_execution=true`
- `approved_primitive_source_import_executes_post=false`
- `approved_primitive_source_construct_executes_post=false`
- `approved_primitive_source_summary_executes_post=false`
- `approved_primitive_boundary_compatible`
- `controlled_binding_compatible`
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

## Source Contract

The boundary is constructed with a caller-supplied source:

```text
construct_live_order_real_one_shot_post_approved_primitive_source_controlled(
  source=...
)
```

Construction does not call the source. Importing the module, rendering the
summary, or constructing the boundary does not POST.

The constructed `approved_primitive_source` can be passed to:

```text
construct_live_order_real_one_shot_post_approved_primitive_controlled(
  primitive=source_boundary.approved_primitive_source
)
```

The source is acceptable only when the contract says:

- approved primitive source supplied
- approved primitive boundary compatible
- controlled binding compatible
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

If any contract flag is unsafe, the source boundary fails closed and the
controlled callable returns a sanitized failed outcome without calling the
source candidate.

## Controlled Binding Compatibility

The intended chain for the next execution gate is:

```text
approved source boundary
  -> approved primitive boundary
  -> controlled real transport binding
  -> controlled one-shot executor
```

The approved primitive boundary, binding, and executor still own their own
guards. Tests verify the chain using fake/monkeypatch sources only.

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
- reuse a previous POST-specific confirmation
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
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-5
```

That step must first confirm the repository state and prerequisite gates, show
the sanitized executable order preview, then obtain a new POST-specific explicit
confirmation in the current Codex session. The confirmation from RETRY-4 is not
reusable. Only after those checks may it consider one HTTP POST through the safe
route, approved primitive source boundary, approved primitive boundary, and
controlled binding.

The next step must still keep these boundaries separate:

- HTTP POST and retry/repost
- HTTP POST and ledger update
- HTTP POST and attempt counter persistence
- HTTP POST and actual result receipt
- actual receipt handoff and any future order action
