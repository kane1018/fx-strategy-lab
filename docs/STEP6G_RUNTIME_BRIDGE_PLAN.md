# Step 6G Runtime Bridge Fake Executor Plan

## Summary

Step 6G-EB adds a fake-only runtime bridge on top of the Step 6G-PB POST route
bridge pure model. It accepts a ready Step 6G route bridge result and verifies
that a future execution boundary can consume it without crossing live execution
paths.

This step still does not execute API calls, fresh preflight, HTTP POST, an order
endpoint, broker code, `live_order_once`, or a real order.

## Relationship To Step 6G-PB

Step 6G-PB created the pure route bridge:

- Step 6G final confirmation evidence;
- Step 6B/6C approval artifact evidence;
- final-confirmation and POST-immediate preflight evidence;
- one-shot attempt state;
- route safety evidence.

Step 6G-EB does not replace that model. It consumes the ready result and models
a fake runtime handoff, preserving the same safety defaults.

## Runtime Bridge Scope

The runtime bridge adds:

- `LiveOrderRealStep6GRuntimeBridgeRequest`;
- `LiveOrderRealStep6GFakePostExecutorResult`;
- `LiveOrderRealStep6GRuntimeBridgeResult`;
- `build_live_order_real_step6g_runtime_bridge`;
- `run_live_order_real_step6g_fake_runtime_bridge`;
- `render_live_order_real_step6g_runtime_bridge_markdown`.

All of these are fake/sanitized models. They do not import HTTP clients, broker
code, Private API clients, or `live_order_once`.

## Fake Executor Meaning

Fake categories are:

- `FAKE_POST_ACCEPTED_NO_API_NO_POST`;
- `FAKE_POST_REJECTED_NO_RETRY_NO_API_NO_POST`;
- `FAKE_POST_RESULT_UNKNOWN_NO_RETRY_NO_API_NO_POST`;
- `FAKE_POST_TIMEOUT_NO_RETRY_NO_API_NO_POST`.

These are not real POST outcomes. They only prove that the runtime bridge can
handle fake accepted, rejected, unknown, and timeout branches without retry,
loop, raw/secret/ID exposure, or live execution.

## Ready And Completed Statuses

Ready without running the fake executor:

```text
STEP6G_RUNTIME_BRIDGE_FAKE_READY_NO_API_NO_POST
```

Fake executor completed:

```text
STEP6G_RUNTIME_BRIDGE_FAKE_COMPLETED_NO_API_NO_POST
```

Both keep:

- `allowed_for_live=false`;
- `post_allowed_this_step=false`;
- `post_executed=false`;
- `real_http_post_executed=false`;
- `order_endpoint_called=false`;
- `live_order_once_called=false`;
- `broker_order_path_called=false`;
- retry/loop/add/change/cancel/close disabled.

## Blocked Conditions

The runtime bridge blocks if:

- the Step 6G-PB route bridge is not ready;
- final confirmation is missing, not exact, or reused;
- approval artifact evidence is missing or not exact-match ready;
- either preflight snapshot is missing or failed;
- `post_attempt_limit != 1`;
- `post_attempt_count_before != 0`;
- fake attempt count exceeds one;
- fake executor tries to retry or loop;
- fake executor tries to mark real HTTP POST, order endpoint, broker path, or
  `live_order_once` as called;
- Step 4 approval phrase or ledger state is spoofed or reused;
- raw request, raw response, header, signature, credential, or real ID exposure
  is represented.

## Step 4 Boundary

Step 6G-EB does not treat Step 6G final confirmation as a Step 4 approval
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
- a reviewed real adapter that keeps one POST maximum;
- no retry, no loop, no add, no change, no cancel, no close;
- sanitized reconciliation only after any real POST attempt.

Old final confirmation phrases remain invalid and must not be reused.

## Tests

Tests cover the fake accepted/rejected/unknown/timeout paths, bridge-not-ready,
approval, preflight, attempt-state, route-safety, raw/secret/ID exposure, retry
or loop blockers, renderer warnings, sanitized serialization, and AST import
guards proving the new module does not import HTTP client, broker, Private API,
or `live_order_once`.
