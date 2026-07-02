# Step 6G One-Shot POST Ledger-Free Source Factory Controlled

Step 6G-PC-OX-R-LEDGER-FREE-POST-ONLY-SOURCE-FACTORY-C implements the
ledger-free POST-only source factory foundation for the controlled one-shot
POST path.

This step is not actual HTTP POST, not an order endpoint call, not
`live_order_once` execution, not a POST-specific confirmation step, and not a
ledger or receipt step.

## Scope

Implemented in:

- `backend/app/live_verification/live_order_real_one_shot_post_ledger_free_source_factory_controlled.py`

The factory composes:

1. sealed request/body/result foundation
2. sealed credential/signing/header provider foundation
3. safe result mapper
4. controlled source callable factory
5. approved primitive actual source current/default route connection

The module does not import or call:

- `live_order_once`
- broker clients
- Private API clients
- HTTP clients
- env readers
- credential readers
- real signing helpers
- real header builders
- ledger writers
- receipt handoff code

## Safe Summary

The factory summary exposes only safe labels, statuses, booleans, counts, and
blocked reason labels:

- `ledger_free_post_only_source_factory_ready`
- `factory_default_no_execution=true`
- `factory_import_executes_post=false`
- `factory_construct_executes_post=false`
- `factory_summary_executes_post=false`
- `factory_requires_sealed_request=true`
- `factory_requires_sealed_body=true`
- `factory_requires_sealed_credential_signing_provider=true`
- `factory_requires_safe_result_mapper=true`
- `factory_requires_post_specific_confirmation=true`
- `factory_produces_controlled_source_callable`
- `approved_primitive_actual_source_available`
- `actual_http_post_executed=false`
- `retry_allowed=false`
- `ledger_update_allowed=false`
- `receipt_handoff_allowed=false`

It never exposes credential values, signature values, headers values, raw
request or response values, broker/API responses, account/order/transaction
IDs, client order ID values, ledger state, or confirmation values.

## Controlled Source Callable

The factory can construct a controlled source callable and connect it to:

```text
construct_live_order_real_one_shot_post_approved_primitive_actual_source_controlled(
  actual_source=...
)
```

Construction does not call the source. Importing the module, rendering the
summary, constructing the factory, or constructing the source callable does not
POST.

The callable:

- is intended to be invoked only by the controlled executor path
- does not retry internally
- does not update ledgers
- does not persist attempt counters
- does not hand off receipts
- maps timeout, unknown, unavailable, and failed outcomes fail-closed
- sanitizes any unsafe fake/monkeypatch outcome before it can propagate

The default constructed callable is fail-closed when no delegate is supplied.
`Step 6G-PC-OX-R-REAL-POST-DELEGATE-CONNECTION-C` adds the controlled delegate
connection and records whether the source callable is missing a delegate without
executing POST. Tests use fake/monkeypatch delegates only to verify exactly-once
connection and safe mapping.

## Current/Default Route

The approved primitive actual source module now exposes a current/default
route helper:

```text
build_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled()
construct_current_live_order_real_one_shot_post_approved_primitive_actual_source_controlled()
```

These helpers lazily connect the delegate-backed ledger-free factory path to the
approved primitive actual source boundary without executing POST.

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
- read `.env` or env files
- display credentials, signatures, headers, raw data, IDs, or confirmation text

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-8
```

That later step must still start by confirming repository state and
prerequisites, showing the sanitized executable order preview, and obtaining a
new POST-specific explicit confirmation in the current Codex session before any
one-shot POST can be considered. Ledger update, attempt counter persistence,
actual receipt handoff, retry, and repost remain separate and forbidden.
