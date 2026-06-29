# Step 6G POST Route Bridge Plan

## Summary

Step 6G-PB adds a pure Step 6G POST route bridge model. It connects sanitized
Step 6G final confirmation evidence, Step 6B/6C approval artifact evidence,
fresh preflight evidence, one-shot attempt state, and route safety evidence into
one fail-closed bridge decision.

This bridge does not execute a POST. It only decides whether the Step 6G
evidence is coherent enough for a future separate execution task to consider a
controlled one-shot route.

## Why This Bridge Exists

Step 6G-F2 reached these gates:

- final confirmation exact match received;
- approval artifact regenerated;
- fingerprint and sha256 prefix matched;
- POST-immediate fresh preflight passed;
- order intent exact match passed for `USD_JPY BUY 100 MARKET`.

It stopped with `BLOCKED_STEP6GF2_ROUTE_UNSAFE` because the existing
`live_order_once.py` primitive is a Step 4 path. It requires a Step 4 approval
phrase and a Step 4 prepared ledger state. Step 6G final confirmation and the
Step 6B/6C approval artifact are not the same contract.

## Scope

The new pure model is:

- `LiveOrderRealStep6GOrderIntentSnapshot`;
- `LiveOrderRealStep6GApprovalSnapshot`;
- `LiveOrderRealStep6GPreflightSnapshot`;
- `LiveOrderRealStep6GAttemptState`;
- `LiveOrderRealStep6GRouteContractSnapshot`;
- `LiveOrderRealStep6GPostRouteBridgeResult`;
- `build_live_order_real_step6g_post_route_bridge`;
- `render_live_order_real_step6g_post_route_bridge_markdown`.

## What This Step Does

- Checks that the order intent is exactly `USD_JPY BUY 100 MARKET`.
- Checks that Codex did not infer or change symbol, side, size, or execution
  type.
- Checks that Step 6G final confirmation was received in the same future
  execution step and was an exact match.
- Blocks reuse of an old final confirmation phrase.
- Checks that the Step 6B/6C approval artifact evidence is reestablished,
  validated, exact-match ready, and summarized only by fingerprint and sha256
  prefix.
- Checks that both final-confirmation and POST-immediate preflights are
  represented by sanitized pass snapshots.
- Checks market, positions, active orders, ticker spread/age, permission,
  IP/account binding, and previous-result-unknown flags.
- Checks `post_attempt_limit=1` and `post_attempt_count_before=0`.
- Keeps `post_allowed_this_step=false` because this step is not an execution
  step.
- Requires either a Step 6G dedicated attempt state or an explicit safe adapter
  contract.
- Blocks Step 4 approval phrase spoofing, Step 4 ledger mutation, raw/secret/ID
  exposure, retry, loop, add, change, cancel, or close paths.

## What This Step Does Not Do

- It does not call real API.
- It does not call read-only API.
- It does not call public API.
- It does not call Private API.
- It does not call broker code.
- It does not execute fresh preflight.
- It does not call an order endpoint.
- It does not generate or send an order payload.
- It does not execute HTTP POST.
- It does not call `live_order_once`.
- It does not read or mutate ledgers.
- It does not display or save raw request, raw response, headers, signatures,
  credentials, real IDs, or a full approval command.

## Step 4 Boundary

The bridge deliberately does not treat Step 6G final confirmation as a Step 4
approval phrase. It also does not create a fake Step 4 phrase and does not force
Step 4 ledger state.

Future runtime work may reuse safe low-level concepts from prior one-shot work,
but it must do so through an explicit Step 6G contract. Any direct Step 4
approval/ledger reuse without that contract remains blocked.

## Ready Meaning

Ready status is:

```text
STEP6G_POST_ROUTE_BRIDGE_READY_NO_API_NO_POST
```

Ready means:

- `bridge_ready=true`;
- `eligible_for_future_step6g_execution_attempt=true`;
- `no_api_executed=true`;
- `no_post_executed=true`;
- `order_endpoint_called=false`;
- `live_order_once_called=false`;
- `allowed_for_live=false`;
- `post_allowed_this_step=false`;
- `post_executed=false`.

Ready is not live execution permission. It does not authorize reuse of any old
final confirmation. A future execution attempt must start as a separate Step 6G
task, regenerate approval evidence, run fresh preflight, show a new final gate,
and receive a new exact final confirmation phrase.

## Blocked Statuses

- `BLOCKED_STEP6G_BRIDGE_ORDER_INTENT`
- `BLOCKED_STEP6G_BRIDGE_APPROVAL`
- `BLOCKED_STEP6G_BRIDGE_PREFLIGHT`
- `BLOCKED_STEP6G_BRIDGE_ATTEMPT_STATE`
- `BLOCKED_STEP6G_BRIDGE_ROUTE_UNSAFE`
- `BLOCKED_STEP6G_BRIDGE_STEP4_SPOOFING`
- `BLOCKED_STEP6G_BRIDGE_RAW_OR_SECRET_EXPOSURE`
- `BLOCKED_STEP6G_BRIDGE_UNSUPPORTED`

## Safety Defaults

- `allowed_for_live=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `retry_allowed=false`
- `loop_allowed=false`
- `add/change/cancel/close=false`

## Future Execution Requirements

Before any future Step 6G execution task can attempt a POST, it still needs:

- a new explicit Step 6G execution request;
- a new final confirmation gate;
- a new exact final confirmation phrase entered in that task;
- approval artifact regeneration and fingerprint/sha256 prefix match in that
  task;
- final-confirmation and POST-immediate fresh preflight checks in that task;
- `post_attempt_count_before=0`;
- one POST maximum;
- no retry, no loop, no add, no change, no cancel, no close;
- sanitized reconciliation only after a POST attempt.

## Tests

Tests cover ready snapshots, approval blockers, old final confirmation reuse,
Step 4 spoofing, order intent mismatch, preflight failure, attempt-state
failure, route unsafe paths, raw/secret/ID exposure, renderer warnings,
serialization safety, and AST checks proving no HTTP client, broker, Private
API, or `live_order_once` imports.
