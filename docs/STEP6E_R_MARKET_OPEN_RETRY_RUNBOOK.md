# Step 6E-R Market-open Real API Preflight Retry Runbook

## Summary

Step 6E-R is the market-open retry procedure for Step 6E real API preflight.
It may run one read-only/preflight confirmation only after a separate explicit
request during market hours. This runbook is preparation only; Step 6E-S does
not execute any API.

Step 6E-R is read-only/preflight only, no POST, no order endpoint, and no
`live_order_once`. A ready Step 6E-R result still keeps `allowed_for_live=false`
and does not authorize live POST.

## Current status

- Step 6E model, tests, and docs are implemented.
- Step 6E real API preflight has not been executed.
- The Step 6E implementation pass stopped because the work date was
  2026-06-28 Sunday JST.
- `allowed_for_live=false` remains mandatory.
- HTTP POST, real orders, order endpoints, `live_order_once`, raw request/raw
  response display or save, headers/signature display or save, and credential
  display remain prohibited.

## Why Step 6E real API was not executed on Sunday

Sunday JST is a market/weekend blocker. Step 6E must fail closed before real
API execution when it is weekend, market-hours are unknown, the market is
closed, broker maintenance is suspected, or the safe read-only route cannot be
verified.

## Retry scope

Step 6E-R may be used tomorrow or later, during market hours, as a separate
explicit task. It may perform at most one verified read-only/preflight
confirmation and must report only sanitized extracted fields.

Step 6E-R must not proceed to Step 6F automatically. Step 6F requires a
separate explicit request. One-shot POST remains Step 6G or later.

## What this retry may do

- Confirm the repository is clean.
- Re-run the required tests, ruff, and danger/secret checks.
- Confirm local market-hours/weekend prefilter is safe.
- Confirm a safe read-only/preflight route exists.
- Confirm the route does not use POST, order endpoints, or `live_order_once`.
- Confirm the route does not display or save raw output.
- Execute one read-only/preflight confirmation only if every gate is safe.
- Report sanitized fields only.

## What this retry must not do

- Set `allowed_for_live=true`.
- Execute HTTP POST.
- Place, add, close, cancel, or change orders.
- Connect to any order endpoint.
- Generate or send an order payload.
- Call `live_order_once`.
- Show or save raw request or raw response.
- Show or save headers or signatures.
- Show credentials or real IDs.
- Show copyable approval command text.
- Use `pbcopy`.
- Read or modify ledgers.
- Retry, loop, add, change, cancel, or close.

## Required preconditions

- Explicit Step 6E-R request is present.
- Operator acknowledgements are complete.
- Current day is not weekend JST.
- Market-hours prefilter is safe and not unknown.
- Broker maintenance is not suspected.
- `git status` is clean.
- Required tests pass.
- `ruff check .` passes.
- Danger/secret scan is clean or only known safe field names/docs/test dummy
  terms are present.
- Safe read-only route is verified.
- No POST, no order endpoint, no `live_order_once`, and no raw output are
  verified.

## Market-hours / weekend blocker

Stop before real API execution when any of the following is true:

- weekend JST;
- market closed;
- market-hours unknown;
- broker maintenance suspected;
- holiday or special close is active or unknown;
- local prefilter cannot prove the market window is safe.

## Safe read-only route confirmation

Before any read-only/preflight call, confirm the route:

- is read-only/preflight only;
- does not use POST;
- does not call order endpoints;
- does not call `live_order_once`;
- does not emit raw request or raw response;
- does not emit headers, signatures, credentials, or real IDs;
- returns only sanitized fields.

If any route boundary is unclear, Step 6E-R must stop.

## Raw response / headers / signature policy

The retry must keep these flags false:

- `raw_request_saved=false`
- `raw_request_displayed=false`
- `raw_response_saved=false`
- `raw_response_displayed=false`
- `headers_saved=false`
- `headers_displayed=false`
- `signature_saved=false`
- `signature_displayed=false`
- credentials and real IDs displayed false

## Execution sequence

1. Confirm explicit Step 6E-R request and acknowledgements.
2. Confirm clean Git state.
3. Run the required tests, ruff, and danger/secret checks.
4. Confirm the current JST day is not weekend and market-hours are safe.
5. Confirm the safe read-only/preflight route and all no-order/no-raw-output
   boundaries.
6. Stop if any value is unknown.
7. Execute at most one read-only/preflight confirmation through the verified
   route.
8. Do not display or save raw output.
9. Populate the Step 6E model with sanitized fields only.
10. Report sanitized results and stop.

## Stop conditions

Stop without real API execution if:

- market is closed, weekend, maintenance, holiday, or unknown;
- safe route is missing or unclear;
- order endpoint boundary is unclear;
- raw response cannot be kept hidden and unsaved;
- headers, signatures, credentials, or real IDs may be exposed;
- POST, retry, loop, add, change, cancel, or close would be needed;
- `live_order_once` would be needed;
- `.env` display or env listing would be needed;
- any required status is unknown.

## Sanitized result fields

Allowed sanitized fields include:

- `market_session_state`
- `market_window_allowed`
- `account_asset_status`
- `open_positions_count`
- `active_orders_count`
- `instrument_symbol`
- `instrument_min_open_order_size`
- `instrument_size_step`
- `ticker_symbol`
- `ticker_spread_jpy`
- `ticker_age_seconds`
- `permission_scope_check_passed`
- `ip_account_binding_check_passed`
- `previous_result_unknown_check_passed`

## Pass meaning

Pass means only that the read-only/preflight sanitized result can be handed to
a future Step 6F post-readiness planning request. It is not live POST
permission, not approval to trade, and not permission to call an order
endpoint. `allowed_for_live=false` remains fixed.

## Blocked meaning

Blocked means Step 6E-R did not produce safe sanitized preflight evidence. It
must not be retried in a loop. Fix the named blocker or wait for a safe market
window, then request a separate retry.

## Future Step 6F handoff

Step 6F requires a separate explicit request. It must re-check freshness,
market-hours, zero open positions, zero active orders, spread, ticker age,
permissions, IP/account binding, and raw-output safety. Step 6F remains no
POST unless separately scoped. One-shot POST remains Step 6G or later.

## Step 6E-RR route review result

Step 6E-RR reviewed the current route candidates offline and did not execute
API calls. It found that the existing private readonly script and public
market-data adapter are not enough as one complete Step 6E-R route. Before
Step 6E-R2, add a safe consolidated route or wrapper that covers the missing
sanitized fields without raw output, POST, order endpoints, or
`live_order_once`.

## Final report format

The Step 6E-R final report should include:

- whether real API preflight was executed;
- if not executed, the exact blocker;
- safe route name if executed;
- sanitized fields only if executed;
- confirmation that no POST, no order endpoint, no `live_order_once`, no raw
  request/response display or save, no headers/signatures/credentials display,
  and no real IDs display occurred;
- test, ruff, danger/secret, and Git results;
- next step: explicit Step 6F request only.
