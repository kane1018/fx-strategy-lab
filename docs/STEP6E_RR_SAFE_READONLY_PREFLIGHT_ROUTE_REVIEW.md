# Step 6E-RR Safe Read-only Preflight Route Review

## Summary

Step 6E-RR is an offline/static review of read-only/preflight route candidates
after Step 6E-R stopped with `BLOCKED_STEP6E_PREFLIGHT_ENVIRONMENT`.

Conclusion: the current repository has safe-looking GET candidates, but no
single verified Step 6E-R route covers all required sanitized fields. The next
work should be a safe route consolidation implementation, still no API and no
POST until separately scoped.

## Scope

This step reviews route metadata, source files, docs, and tests only. It adds a
static `LiveOrderRealApiPreflightSafeRouteReview` model for route coverage and
gap tracking.

## What this step does

- records existing read-only/preflight route candidates;
- checks static no-POST/no-order/no-raw-output route flags;
- builds a Step 6E-R required coverage matrix;
- lists missing fields;
- defines data handling policy;
- decides whether Step 6E-R2 can use an existing route or needs consolidation.

## What this step does not do

Step 6E-RR does not call real API, read-only API, public API, Private API,
broker code, order endpoints, or `live_order_once`. It does not execute HTTP
POST, create order payloads, display or save raw request/response, display or
save headers/signatures/credentials, read ledgers, or change `.env`.

## Step 6E-R blocker

Step 6E-R confirmed market timing, Git state, tests, and ruff, but stopped
before real API preflight because a single verified safe read-only/preflight
route was not available. The blocker was not market timing; it was route
coverage and route consolidation evidence.

## Existing route candidates

`backend/scripts/check_private_readonly_connection.py`:

- private GET candidate for `account/assets`, `openPositions`, and
  `activeOrders`;
- designed to print sanitized flags/counts rather than raw response/header or
  credential values;
- does not cover market-hours, instrument rules, ticker spread/age, permission
  scope, IP/account binding, or previous-result-unknown state;
- was reviewed statically only and was not executed in Step 6E-RR.

`backend/app/shadow/gmo_public.py`:

- public GET adapter candidate for status/ticker/klines source data;
- no auth and no Private API path;
- not a complete Step 6E sanitized result route;
- does not cover account assets, positions, active orders, instrument rules,
  permission scope, IP/account binding, or previous-result-unknown state;
- was reviewed statically only and was not executed in Step 6E-RR.

## Route safety review

Safe route candidates must keep all of these false:

- `uses_http_post`
- `uses_order_endpoint`
- `uses_live_order_once`
- `uses_speed_order`
- `uses_close_order`
- `uses_cancel_order`
- `uses_change_order`
- `uses_broker_order_path`
- raw request/response display or save flags
- headers/signature display or save flags
- credential display flags
- `.env` display requirements

They must return sanitized fields only.

## Required coverage matrix

Covered by current candidates or static policy:

- `account_asset_status`
- `account_asset_check_passed`
- `open_positions_count`
- `open_positions_check_passed`
- `active_orders_count`
- `active_orders_check_passed`
- `market_session_state`
- `ticker_symbol`
- raw request/response/header/signature/credential/real-ID non-exposure flags

Missing from a complete single Step 6E-R safe route:

- `market_window_allowed`
- `broker_maintenance_active`
- `holiday_or_special_close`
- `market_hours_unknown`
- `instrument_symbol`
- `instrument_min_open_order_size`
- `instrument_size_step`
- `instrument_rule_check_passed`
- `ticker_spread_jpy`
- `ticker_age_seconds`
- `ticker_check_passed`
- `permission_scope_check_passed`
- `ip_account_binding_check_passed`
- `previous_result_unknown_check_passed`

## Missing fields

Missing fields require a future safe wrapper or consolidated route that extracts
only sanitized values, never prints raw response/header/signature/credential
values, and never touches order endpoints or `live_order_once`.

## Data handling policy

The Step 6E-RR policy fixes:

- `raw_request_display_allowed=false`
- `raw_request_save_allowed=false`
- `raw_response_display_allowed=false`
- `raw_response_save_allowed=false`
- `headers_display_allowed=false`
- `headers_save_allowed=false`
- `signature_display_allowed=false`
- `signature_save_allowed=false`
- `credentials_display_allowed=false`
- `credentials_save_allowed=false`
- real order/execution/position/client-order ID display false
- `sanitized_fields_only=true`
- `git_commit_real_api_results=false`

## Review status

The current static review status is:

`READY_FOR_STEP6E_SAFE_ROUTE_CONSOLIDATION_IMPLEMENTATION`

Meaning:

- safe GET candidates exist;
- required Step 6E-R coverage is incomplete;
- Step 6E-R2 is not yet eligible with the existing routes alone;
- the next step should implement a safe consolidated route or wrapper before
  any Step 6E-R2 retry.

## If existing safe route is complete

If a future review proves all required fields are covered by existing safe
routes, the status may become
`READY_FOR_STEP6E_R2_RETRY_WITH_EXISTING_SAFE_ROUTE`. That status still does
not permit POST, order endpoints, `live_order_once`, raw output, or
`allowed_for_live=true`.

## If consolidation implementation is needed

The next implementation step should build a wrapper that joins existing safe
GET candidates and static/local status into one sanitized Step 6E result
surface. It must remain no API/no POST unless the later execution step
explicitly scopes a single read-only/preflight call.

## If route is incomplete or unsafe

Incomplete means the required field source, raw-output policy, or route
boundary is not proven. Unsafe means POST, order endpoint, `live_order_once`,
raw response display, or credential display would be required. Either state
blocks Step 6E-R2.

## Future Step 6E-R2 handoff

Step 6E-R2 needs either a complete existing safe route or a completed safe route
consolidation implementation. Step 6E-R2 remains read-only/preflight only,
single-shot, no POST, no order endpoint, no `live_order_once`, no raw
request/response display or save, and `allowed_for_live=false`.

## Future safe route consolidation implementation handoff

Implement a consolidated sanitized route that covers market-hours, account
assets, open positions, active orders, instrument rules, ticker spread/age,
permission scope, IP/account binding, previous-result-unknown, and non-exposure
flags. Do not modify broker/order paths, do not add POST, and do not store raw
API outputs.

## Tests

Tests cover complete existing route readiness, partial safe route consolidation
readiness, incomplete evidence, unsafe route flags, required coverage matrix,
missing field preservation, data policy, offline/no-API/no-POST flags,
Markdown warnings, serialization safety, and no-order import boundaries.

## Handoff summary

Step 6E-RR is complete when the route review model, coverage matrix, docs, and
tests show that existing candidates are not enough for Step 6E-R2 without a
safe consolidation implementation. Step 6F remains blocked.

## Step 6E-SC follow-up

Step 6E-SC implements the safe consolidation wrapper/model recommended by this
review. It accepts sanitized private read-only, public market, and local/static
inputs and produces a single consolidated sanitized result without calling any
API. A ready Step 6E-SC result is eligible only for a future Step 6E-R2 retry;
Step 6F remains blocked until fresh Step 6E-R2 evidence exists.
