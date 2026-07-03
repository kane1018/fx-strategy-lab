# Step 6G Official Settlement Actual POST Live Enablement No-POST

This document records
`Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-ACTUAL-POST-LIVE-ENABLEMENT-NO-POST-C`.

## Scope

This step resolves the previous execution gate blocker where the dedicated
official settlement transport was detectable but no-POST only. It adds a
settlement-specific live-capable enablement simulation that can prove the next
execution gate may set `actual_settlement_post_allowed_now=true` only after all
fresh execution gates are satisfied.

This step does not execute settlement POST, entry POST, generic close POST,
generic opposite order, retry, repost, second settlement, ledger update,
receipt handoff, broker write, raw request/response handling, ID handling,
credential values, signature values, or header values.

## Blocker Resolved

The prior execution gate stopped before settlement POST because the current
dedicated actual settlement transport boundary remained no-POST only:

```text
actual_settlement_post_allowed_now=false
actual_settlement_post_executed=false
settlement_post_count=0
```

This step adds live-capable enablement while keeping this step no-POST:

```text
actual_settlement_post_live_capable_transport_available=true
actual_settlement_post_can_be_allowed_after_fresh_execution_gates=true
execution_gate_simulation_can_set_actual_settlement_post_allowed_now=true
execution_gate_simulation_uses_fake_transport=true
execution_gate_simulation_http_post_executed=false
this_step_actual_settlement_post_allowed_now=false
this_step_actual_settlement_post_executed=false
settlement_post_count=0
```

## Required Execution Gates

The simulation allows `actual_settlement_post_allowed_now=true` only when all of
the following safe gates are true:

```text
repository_clean=true
HEAD_equals_origin_main=true
credential_presence_available=true
runtime_position_status=ONE_POSITION_OPEN
position_count_safe=1
has_exactly_one_position=true
has_multiple_positions=false
operator_broker_ui_checked=true
operator_broker_ui_open_position_visible=true
operator_broker_ui_values_or_ids_provided=false
operator_can_monitor=true
operator_approves_settlement_attempt=true
sanitized_settlement_preview_shown=true
settlement_specific_confirmation_current_turn=true
settlement_specific_confirmation_exact_match=true
```

Any missing repository, credential, runtime position, operator readiness,
preview, confirmation, route, transport, or safety gate fails closed.

## Dedicated Settlement Route

The live enablement remains settlement-specific and separated from generic
order execution:

```text
settlement_route_kind=OFFICIAL_SIZE_BASED_SETTLEMENT
settlement_route_is_generic_order=false
settlement_route_is_dedicated=true
generic_order_executor_used_for_settlement=false
live_order_once_used_for_settlement=false
generic_order_endpoint_used_for_settlement=false
one_shot_generic_order_path_used_for_settlement=false
position_specific_path_used=false
position_specific_identifier_safe_handling_ready=false
position_specific_preview_allowed=false
size_based_preview_allowed=true
```

## No-POST Safety

The live-capable path is tested with a fake transport. It proves authorization
logic only; it does not call a broker endpoint in this step.

```text
execution_gate_simulation_uses_fake_transport=true
execution_gate_simulation_http_post_executed=false
transport_call_count=0
http_post_executed=false
entry_post_executed=false
generic_close_post_executed=false
retry_allowed=false
repost_allowed=false
second_settlement_allowed=false
ledger_update=false
receipt_handoff=false
raw_id_value_credential_header_exposure=false
```

## Next Execution Gate

Recommended next step:

```text
Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C
```

That future step must still perform fresh repository checks, credential
presence safe boolean checks, fresh runtime `ONE_POSITION_OPEN / count=1`
confirmation, operator readiness, sanitized settlement preview, and a new
settlement-specific confirmation before any actual settlement POST can be
considered.

## Unsafe Data Boundary

This document does not contain raw request/response data, broker/API responses,
account/order/transaction/position/trade IDs, credential values, signature
values, header values, actual market prices, or PnL values.
