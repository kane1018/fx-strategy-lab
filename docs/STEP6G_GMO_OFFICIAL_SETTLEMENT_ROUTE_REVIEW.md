# Step 6G GMO Official Settlement Route Review

This document records
`Step 6G-PC-OX-R-GMO-OFFICIAL-SETTLEMENT-ROUTE-REVIEW-C`.

## Scope

This step is official-document and existing-code review only. It does not
execute entry POST, close POST, retry, repost, second close, order endpoint
calls, `live_order_once`, ledger updates, receipt handoff, broker writes, or
raw/ID/value handling.

## Official References

```text
GMO FX operation manual:
https://coin.z.com/corp_imgs/manual/kawasefx-trading-manual.pdf

GMO FX trading rules:
https://coin.z.com/jp/corp/product/info/fx/#rule

GMO FX API docs:
https://api.coin.z.com/fxdocs/
```

## Manual Review

Safe summary:

```text
official_manual_accessed=true
manual_settlement_flow_found=true
manual_position_summary_settlement_button_found=true
manual_position_list_settlement_button_found=true
manual_buy_sell_not_netted_confirmed=true
manual_generic_opposite_order_as_settlement_supported=false
manual_review_raw_text_exposed=false
```

The operation manual describes settlement from position summary/list controls.
It also confirms that buy and sell positions are displayed separately and are
not netted when hedged.

## Trading Rules Review

Safe summary:

```text
official_rules_accessed=true
official_rules_api_new_order_min_confirmed=true
official_rules_settlement_quantity_no_lower_limit_confirmed=true
official_rules_hedging_possible_confirmed=true
official_rules_trading_time_recorded=true
official_rules_order_reception_time_recorded=true
rules_review_raw_text_exposed=false
```

The trading rules keep API new-order minimums separate from settlement quantity
rules. They also confirm hedging is possible.

## Official API Settlement Review

The official GMO FX API docs identify a dedicated close-order settlement route
and settlement parameters. This is not the generic order route used for new
positions.

Safe summary:

```text
official_api_docs_accessed=true
repo_official_api_docs_found=true
repo_settlement_endpoint_found=true
repo_settlement_parameter_found=true
repo_settlement_requires_position_identifier=false
official_settlement_size_without_position_identifier_confirmed=true
repo_settlement_safe_identifier_handling_ready=false
repo_generic_order_endpoint_only=false
repo_generic_order_is_not_settlement=true
```

Position-specific settlement can require a position selection identifier. That
identifier handling is not implemented here and must remain fail-closed until a
separate no-raw-ID design exists. The size-based dedicated settlement route is
confirmed only as official route evidence, not as execution permission.

## Judgement

```text
CASE=CASE 1
official_settlement_route_confirmed=true
official_settlement_route_confirmation_basis=OFFICIAL_SETTLEMENT_ROUTE_CONFIRMED_NO_POST
actual_close_post_allowed_now=false
future_actual_close_post_requires_dedicated_settlement_gate=true
future_actual_close_post_requires_no_raw_id_value_exposure=true
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
```

This means a future no-POST settlement preview may be implemented from the
official dedicated settlement route. It does not permit actual close POST in
this step.

## Level 5 Safety

```text
current_position_state=NO_POSITION_AFTER_MANUAL_FLATTEN
manual_flatten_reconciled=true
level5_minimal_cycle_completed=false
level5_full_auto_cycle_completed=false
fresh_cycle_allowed=false
close_execution_allowed_until_official_route=false
next_cycle_state=OFFICIAL_SETTLEMENT_ROUTE_REVIEWED_NO_POST
```

The prior position risk is flat after manual intervention. The Level 5 full auto
cycle remains incomplete because the previous Codex close attempt used a generic
opposite order and required manual flattening.

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-OFFICIAL-SETTLEMENT-ROUTE-NO-POST-IMPLEMENTATION-C
```

That step must remain no-POST and create only a sanitized dedicated settlement
preview. Actual close POST remains forbidden until a later separate execution
gate with fresh confirmation.

## Unsafe Data Boundary

This document does not contain raw request/response data, broker/API responses,
account/order/transaction/position/trade IDs, credential values, signature
values, header values, actual market prices, or PnL values.
