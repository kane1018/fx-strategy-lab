# Step 6E-SC Safe Read-only Preflight Route Consolidation

## Summary

Step 6E-SC adds a no-API/no-POST consolidation model for Step 6E-R2. It
combines already-sanitized private read-only input, public market input, and
local/static input into one consolidated sanitized result.

Ready consolidation means Step 6E-R2 may be requested with a consolidated safe
route surface. It does not mean Step 6F readiness, live POST permission, or
`allowed_for_live=true`.

## Scope

This step is model/test/docs only. It accepts sanitized values and evaluates
them fail-closed. It does not fetch values from GMO, read `.env`, call broker
code, or run any API path.

## What this step does

- defines private read-only sanitized input;
- defines public market sanitized input;
- defines local/static sanitized input;
- consolidates Step 6E required fields into one sanitized result;
- blocks missing input, unsafe routes, incomplete fields, and failing preflight
  conditions;
- records data handling policy and Step 6E-R2 handoff conditions.

## What this step does not do

Step 6E-SC does not call real API, read-only API, public API, Private API,
broker code, order endpoints, or `live_order_once`. It does not execute HTTP
POST, create or send order payloads, display or save raw request/response,
display or save headers/signatures/credentials, read ledgers, or change `.env`.

## Why this step exists

Step 6E-RR found existing safe-looking GET candidates but no complete single
route for Step 6E-R. Step 6E-SC defines the wrapper/model that can combine
those candidate outputs and local/static checks into one sanitized result before
another market-open retry.

## Input: Private read-only sanitized input

The private input is sanitized and must come from a verified no-POST,
no-order-endpoint, no-`live_order_once`, no-raw-output route. It carries only:

- account asset status and pass flag;
- open positions count and pass flag;
- active orders count and pass flag.

It does not carry raw response, headers, signatures, credentials, or real IDs.

## Input: Public market sanitized input

The public market input is sanitized and must come from a verified no-POST,
no-order-endpoint, no-`live_order_once`, no-raw-output route. It carries only:

- market session/window/maintenance/holiday/unknown flags;
- ticker symbol;
- ticker bid/ask for local spread derivation;
- ticker spread, age, and pass flag.

## Input: Local/static sanitized input

The local/static input carries checks that do not require API execution in this
step:

- instrument symbol, minimum open order size, and size step;
- instrument rule pass flag;
- permission scope pass flag;
- IP/account binding pass flag;
- previous-result-unknown pass flag.

## Output: Consolidated sanitized result

The result uses
`SAFE_READONLY_PREFLIGHT_ROUTE_CONSOLIDATED_NO_API_NO_POST` only when all
inputs are present, route boundaries are verified, all required fields exist,
and all preflight checks pass. It keeps `allowed_for_live=false`.

## Required fields

The consolidated result must include market state, account asset status, open
positions count, active orders count, instrument rule fields, ticker spread and
age, permission/IP/account checks, previous-result-unknown check, and all raw
request/response/header/signature/credential/real-ID non-exposure flags.

## Safety policy

All source routes must verify:

- no POST;
- no order endpoint;
- no `live_order_once`;
- no raw output;
- sanitized output only.

Unknown route safety is blocked.

## Data handling policy

Step 6E-SC fixes:

- raw request display/save false;
- raw response display/save false;
- headers display/save false;
- signatures display/save false;
- credentials display/save false;
- real order/execution/position/client-order ID display false;
- sanitized fields only true;
- API execution allowed this step false;
- POST allowed this step false;
- order endpoint allowed this step false;
- `live_order_once` allowed this step false.

## Ready meaning

Ready means the sanitized wrapper/model result is eligible for a future
explicit Step 6E-R2 market-open retry. It is not live POST permission and is not
Step 6F readiness.

## Blocked missing input meaning

`BLOCKED_SAFE_ROUTE_CONSOLIDATION_MISSING_INPUT` means one or more of private,
public, or local/static sanitized inputs is missing.

## Blocked unsafe route meaning

`BLOCKED_SAFE_ROUTE_CONSOLIDATION_UNSAFE_ROUTE` means a source route boundary
or data policy failed, including no-POST, no-order-endpoint,
no-`live_order_once`, no-raw-output, or sanitized-output-only verification.

## Blocked incomplete fields meaning

`BLOCKED_SAFE_ROUTE_CONSOLIDATION_INCOMPLETE_FIELDS` means a required sanitized
field is missing or unknown.

## Blocked preflight-not-passing meaning

`BLOCKED_SAFE_ROUTE_CONSOLIDATION_PREFLIGHT_NOT_PASSING` means all fields are
present but a preflight condition fails, such as market closed, maintenance,
market unknown, nonzero open positions, nonzero active orders, stale/wide
ticker, failed permission scope, failed IP/account binding, or previous result
unknown.

## Future Step 6E-R2 handoff

Step 6E-R2 needs a separate explicit request. It remains read-only/preflight
only, no POST, no order endpoint, no `live_order_once`, no raw output, no
headers/signatures/credentials/real IDs, and `allowed_for_live=false`.

Step 6E-R2 also requires private read-only route credential presence before any
API attempt. The expected names are `GMO_FX_API_KEY` and `GMO_FX_API_SECRET`.
Step 6E-CP defines that presence check as values-hidden, `.env`-hidden, and
environment-list-hidden. Missing credential presence blocks Step 6E-R2 before
API execution.

## Tests

Tests cover ready consolidation, missing inputs, unsafe route verification,
incomplete fields, failing preflight conditions, data policy, renderer warnings,
serialization safety, and no-order/no-API import boundaries.

## Handoff summary

Step 6E-SC is complete when the wrapper/model can produce a single sanitized
result from sanitized inputs only. It enables a future Step 6E-R2 retry request,
but Step 6F remains blocked until fresh Step 6E-R2 evidence exists and a
separate Step 6F request is made.

## Step 6F post-readiness handoff

After a separate Step 6E-R2 runtime pass, Step 6F may consume the sanitized
preflight evidence as `LiveOrderRealPostReadinessPreflightSnapshot`. Step 6F is
still planning-only: no POST, no order endpoint, no order payload generation or
send, no `live_order_once`, and `allowed_for_live=false`.

Ready Step 6F output only means the project can stop and wait for an explicit
Step 6G one-shot POST request. Step 6G must refresh real API preflight
immediately before any POST decision.
