# Step 6G Controlled Adapter Fake Transport Plan

## Summary

Step 6G-AD adds a controlled adapter skeleton for Step 6G. It sits after the
Step 6G-PB POST route bridge pure model and the Step 6G-EB fake runtime bridge.
This adapter accepts only fake transport in this step.

It does not execute API calls, fresh preflight, HTTP POST, an order endpoint,
broker code, `live_order_once`, or a real order.

## Relationship To Previous Step 6G Models

- Step 6G-PB is the pure route bridge model. It connects final confirmation,
  approval artifact, preflight, attempt state, and route safety evidence.
- Step 6G-EB is the fake runtime bridge / fake executor. It verifies the
  runtime handoff without real execution.
- Step 6G-AD is the controlled adapter skeleton. It checks whether a transport
  contract can be accepted before any future real execution adapter is allowed.

## Controlled Adapter Scope

The new fake-only adapter adds:

- `LiveOrderRealStep6GControlledAdapterRequest`;
- `LiveOrderRealStep6GControlledTransportContract`;
- `LiveOrderRealStep6GControlledTransportResult`;
- `LiveOrderRealStep6GControlledAdapterResult`;
- `build_live_order_real_step6g_controlled_adapter`;
- `run_live_order_real_step6g_controlled_adapter_with_fake_transport`;
- `render_live_order_real_step6g_controlled_adapter_markdown`.

The module does not import HTTP clients, broker code, Private API clients, or
`live_order_once`.

## Transport Contract

Only this transport is allowed in Step 6G-AD:

```text
transport_mode=FAKE_ONLY
```

Fake transport must keep:

- `is_fake_transport=true`;
- `is_real_transport=false`;
- `can_execute_http_post=false`;
- `can_call_order_endpoint=false`;
- `can_call_live_order_once=false`;
- `imports_http_client=false`;
- `imports_private_api=false`;
- `imports_broker=false`;
- `imports_live_order_once=false`;
- raw request/response, headers, signatures, credentials, and real IDs hidden;
- `retry_on_unknown=false`;
- `retry_on_timeout=false`;
- `retry_on_reject=false`;
- `max_attempts=1`.

Real transport is blocked in this step. A future real execution task must add
and review a separate real adapter contract.

## Fake Transport Results

Fake categories are:

- `FAKE_CONTROLLED_ADAPTER_ACCEPTED_NO_API_NO_POST`;
- `FAKE_CONTROLLED_ADAPTER_REJECTED_NO_RETRY_NO_API_NO_POST`;
- `FAKE_CONTROLLED_ADAPTER_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST`;
- `FAKE_CONTROLLED_ADAPTER_TIMEOUT_NO_RETRY_NO_API_NO_POST`.

These are not real POST outcomes. They only prove that the controlled adapter
can process fake accepted, rejected, unknown, and timeout branches without retry,
loop, raw/secret/ID exposure, or live execution.

## Ready And Completed Statuses

Ready without running fake transport:

```text
STEP6G_CONTROLLED_ADAPTER_FAKE_READY_NO_API_NO_POST
```

Fake transport completed:

```text
STEP6G_CONTROLLED_ADAPTER_FAKE_COMPLETED_NO_API_NO_POST
```

Both keep:

- `allowed_for_live=false`;
- `post_allowed_this_step=false`;
- `post_executed=false`;
- `real_http_post_executed=false`;
- `order_endpoint_called=false`;
- `live_order_once_called=false`;
- retry/loop/add/change/cancel/close disabled.

## Blocked Conditions

The controlled adapter blocks if:

- PB route bridge is not ready;
- EB runtime bridge is not fake ready or fake completed;
- final confirmation is missing, not exact, or reused;
- approval artifact evidence is missing or not exact-match ready;
- either preflight snapshot is missing or failed;
- order intent is not exactly `USD_JPY BUY 100 MARKET`;
- `post_attempt_limit != 1`;
- `post_attempt_count_before != 0`;
- fake attempt count exceeds one;
- fake transport tries to retry or loop;
- transport is real;
- transport can execute HTTP POST, call an order endpoint, call
  `live_order_once`, or import HTTP/broker/Private API/live-order modules;
- fake transport marks real HTTP POST, order endpoint, broker path, or
  `live_order_once` as called;
- raw request, raw response, headers, signatures, credentials, or real IDs are
  represented;
- Step 4 approval phrase or ledger state is spoofed or reused.

## Step 4 Boundary

Step 6G-AD does not treat Step 6G final confirmation as a Step 4 approval
phrase. It does not create a fake Step 4 phrase and does not mutate Step 4
ledger state.

## Future Real Execution Requirements

A future real Step 6G execution still needs:

- a separate explicit Step 6G execution request;
- a new final confirmation gate;
- a new exact final confirmation phrase;
- approval artifact regeneration and fingerprint/sha256 prefix match in that
  same future task;
- fresh final-confirmation and POST-immediate preflight checks;
- a reviewed real adapter contract;
- one POST maximum;
- no retry, no loop, no add, no change, no cancel, no close;
- sanitized reconciliation only after any real POST attempt.

Old final confirmation phrases remain invalid and must not be reused.

## Tests

Tests cover fake accepted/rejected/unknown/timeout, PB/EB input readiness,
attempt-state blockers, retry/loop blockers, real transport rejection,
transport capability blockers, raw/secret/ID exposure, renderer warnings,
sanitized serialization, and AST import guards proving the new module does not
import HTTP client, broker, Private API, or `live_order_once`.
