# Step 6G One-Shot POST Real Delegate Controlled

This document records the real POST delegate connection boundary for Step 6G.
It is not POST execution and does not request POST-specific confirmation.

## Scope

`backend/app/live_verification/live_order_real_one_shot_post_real_delegate_controlled.py`
adds a controlled delegate contract for the existing
`post_live_order_with_httpx` primitive. The primitive is kept behind a lazy
runner boundary. Import, construction, summary rendering, runner
materialization, delegate supply, factory construction, and source callable
construction do not call it.

The delegate connection records only safe booleans, statuses, labels, and
categories:

- `real_post_delegate_ready=true`
- `delegate_default_no_execution=true`
- `delegate_import_executes_post=false`
- `delegate_construct_executes_post=false`
- `delegate_summary_executes_post=false`
- `delegate_supply_executes_post=false`
- `delegate_requires_post_specific_confirmation=true`
- `delegate_supplied_to_factory=true`
- `source_callable_unavailable_due_missing_delegate=false`
- `real_post_delegate_runner_materialized=true`
- `real_post_delegate_runner_supplied=true`
- `delegate_runner_missing=false`
- `source_callable_unavailable_due_missing_runner=false`
- `runner_default_no_execution=true`
- `runner_materialization_executes_post=false`
- `runner_supply_executes_post=false`
- `runner_requires_post_specific_confirmation=true`
- `actual_post_allowed=false`

## Factory Connection

The ledger-free source factory now records whether a source delegate is supplied
to the controlled source callable:

- `source_delegate_supplied`
- `source_callable_unavailable_due_missing_delegate`

The current/default approved primitive actual source route uses the
delegate-backed factory construction. The runner is materialized in the
current/default route, but it is still only reachable through the existing
execution controller after a later POST-specific confirmation. This removes the
previous missing delegate and missing runner blockers without executing POST.

## Safety Guarantees

The delegate boundary remains separated from:

- approval phrase validation
- ledger update
- attempt counter persistence
- actual result receipt
- actual receipt handoff
- retry/repost

It does not expose credential values, signature values, headers values, raw
request or response values, broker/API responses, account/order/transaction
IDs, client order ID values, endpoint values, ledger state, or confirmation
values.

Fake/monkeypatch tests verify the delegate can be invoked exactly once through
the controlled executor path, maps safe accepted/rejected/fail-closed categories
through the existing safe result mapper, and does not retry or perform a second
POST.

Additional fake/monkeypatch tests verify:

- runner materialization does not call `post_live_order_with_httpx`
- POST-specific confirmation missing keeps the runner uncalled
- a fake authorized execution calls the fake post reference exactly once
- timeout, failed, unknown, unavailable, accepted, and rejected outcomes remain
  safe summaries

## What This Step Did Not Do

This implementation step did not:

- execute actual HTTP POST
- call an order endpoint
- execute `live_order_once`
- obtain POST-specific confirmation
- reuse prior confirmation
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
Step 6G-PC-OX-R-ONE-SHOT-POST-EXECUTION-GATE-RETRY-9
```

That later step must first confirm repository state and prerequisites, show the
sanitized executable order preview, and obtain a new POST-specific explicit
confirmation in the current Codex session before any one-shot POST can be
considered. Ledger update, attempt counter persistence, actual receipt handoff,
retry, and repost remain separate and forbidden.

Before any POST in that later step, the operator-facing gate must also confirm:

- current time is inside the intended trading window
- broker maintenance window is not active
- the user can monitor the screen during and immediately after the action
- no important scheduled event or major market event is imminent or just passed
- if time or market state is unknown, stop as CASE 2 without POST
