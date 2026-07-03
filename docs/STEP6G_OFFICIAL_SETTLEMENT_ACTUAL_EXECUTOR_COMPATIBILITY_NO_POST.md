# Step 6G Official Settlement Actual Executor Compatibility No-POST

This document records
`Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-ACTUAL-EXECUTOR-COMPATIBILITY-NO-POST-C`.

## Scope

This step connects the existing official size-based settlement no-POST preview
to a dedicated settlement actual-executor compatibility boundary. It does not
execute entry POST, settlement POST, close POST, generic opposite close, retry,
repost, second settlement, order endpoint calls, `live_order_once`, ledger
updates, receipt handoff, broker writes, raw request/response handling, ID
handling, credential values, signature values, or header values.

## Blocker Resolved

The prior execution gate stopped before settlement POST because no dedicated
actual settlement executor compatibility boundary existed. The only executable
POST path in the repo was generic order oriented and is not valid settlement.

This step adds a settlement-specific no-POST compatibility boundary:

```text
dedicated_settlement_actual_executor_compatibility_ready=true
official_settlement_no_post_preview_ready=true
settlement_route_kind=OFFICIAL_SIZE_BASED_SETTLEMENT
settlement_route_is_generic_order=false
settlement_route_is_dedicated=true
generic_order_executor_used_for_settlement=false
live_order_once_used_for_settlement=false
position_specific_path_used=false
position_specific_identifier_safe_handling_ready=false
```

## Runtime Guard

Compatibility is available only for a fresh safe runtime position context:

```text
runtime_position_status=ONE_POSITION_OPEN
position_count_safe=1
has_exactly_one_position=true
has_multiple_positions=false
```

`NO_POSITION`, `MULTIPLE_POSITIONS_BLOCKED`, unknown position states, and count
values other than one fail closed.

## No-POST Transport

The compatibility boundary uses a dedicated settlement no-POST transport
summary. It is not the generic order executor and does not call
`live_order_once`.

```text
actual_settlement_post_executed=false
settlement_post_count=0
transport_call_count=0
retry_allowed=false
repost_allowed=false
second_settlement_allowed=false
entry_post_executed=false
generic_close_post_executed=false
ledger_update=false
receipt_handoff=false
raw_id_value_credential_header_exposure=false
```

## Position-Specific Path

Position-specific settlement remains blocked because safe identifier handling is
not part of this step.

```text
position_specific_path_used=false
position_specific_identifier_safe_handling_ready=false
```

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-EXECUTION-GATE-C
```

That future step must still perform fresh repository checks, credential presence
safe boolean checks, fresh runtime `ONE_POSITION_OPEN / count=1` confirmation,
operator readiness, sanitized settlement preview, and a new settlement-specific
confirmation before any actual settlement POST can be considered.

## Unsafe Data Boundary

This document does not contain raw request/response data, broker/API responses,
account/order/transaction/position/trade IDs, credential values, signature
values, header values, actual market prices, or PnL values.
