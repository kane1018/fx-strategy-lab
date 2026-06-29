# Step 6E Real API Preflight Execution

## Summary

Step 6E adds a fail-closed model for evaluating real API preflight execution
results as sanitized fields only. It consumes the Step 6D
`LiveOrderRealApiPreflightPlan`, an explicit Step 6E request snapshot, an
environment/safe-route check, and a sanitized preflight result.

This step can represent a read-only/preflight check result, but it does not
authorize live POST. Ready Step 6E output keeps `allowed_for_live=false`.

## Scope

Step 6E is read-only/preflight-only result evaluation. It records whether a
sanitized preflight result passed checks for:

- market session/window;
- account asset status;
- open positions count;
- active orders count;
- instrument rule;
- ticker spread and age;
- permission scope;
- IP/account binding;
- previous result unknown state;
- raw request/response/header/signature/ID non-exposure.

## What this step does

- Requires an explicit Step 6E request and operator acknowledgements.
- Requires a ready Step 6D plan.
- Requires an environment check proving market prefilter, clean repo/test/ruff
  state, and a verified safe read-only/preflight route.
- Evaluates sanitized preflight result fields fail-closed.
- Produces `REAL_API_PREFLIGHT_PASSED_NO_POST` only when all inputs are safe.
- Defines future Step 6F handoff conditions and blockers.

## What this step does not do

- It does not execute HTTP POST.
- It does not call an order endpoint.
- It does not generate or send an order payload.
- It does not call `live_order_once`.
- It does not call speed/close/cancel/change order paths.
- It does not issue an approval gate.
- It does not display or save approval command text.
- It does not display or save raw request, raw response, headers, signatures,
  credentials, or real IDs.
- It does not set `allowed_for_live=true`.

## Input: LiveOrderRealApiPreflightPlan

The source plan must be ready from Step 6D:

- `plan_status=API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST`;
- `plan_ready=true`;
- `eligible_for_step6e_real_api_preflight_execution=true`;
- `allowed_for_live=false`;
- no API, broker, `live_order_once`, or POST already called.

Blocked or unsafe source plans produce `BLOCKED_STEP6E_SOURCE_PLAN`.

## Input: RequestSnapshot

`LiveOrderRealApiPreflightExecutionRequestSnapshot` records explicit Step 6E
scope and acknowledgements:

- Step 6E was explicitly requested;
- real-money risk is understood;
- the task is read-only/preflight-only;
- no POST, no order endpoint, and no `live_order_once` are allowed;
- raw response display/save are disallowed;
- Step 6F is separately required for post-readiness planning;
- unknown state means stop.

Missing or incomplete request input produces `BLOCKED_STEP6E_PREFLIGHT_REQUEST`.

## Input: EnvironmentCheck

`LiveOrderRealApiPreflightExecutionEnvironmentCheck` records local preflight
gates before any real read-only/preflight check can be considered:

- Git/tests/ruff/secret scan are clean;
- timezone is `Asia/Tokyo`;
- it is not weekend JST;
- local market-hours prefilter passed;
- a safe read-only/preflight route was found;
- the route is verified as no POST, no order endpoint, no `live_order_once`, no
  raw output, and sanitized-output-only;
- env values and `.env` were not displayed.

Weekend, market-closed/unknown, missing safe route, or raw-output risk produces
`BLOCKED_STEP6E_PREFLIGHT_ENVIRONMENT`.

## Input: SanitizedResult

`LiveOrderRealApiPreflightSanitizedResult` contains only sanitized fields:

- market/session booleans;
- account asset status;
- open positions count;
- active orders count;
- instrument rule summary;
- ticker spread and age;
- permission/IP/account binding booleans;
- previous result unknown check;
- raw/header/signature/credential/ID exposure flags.

Raw request, raw response, headers, signatures, credentials, order IDs,
execution IDs, position IDs, and client order IDs are not accepted as values to
display or persist.

## Output: LiveOrderRealApiPreflightExecution

Ready output uses:

- `execution_status=REAL_API_PREFLIGHT_PASSED_NO_POST`;
- `execution_ready=true`;
- `api_preflight_executed=true`;
- `api_preflight_passed=true`;
- `eligible_for_step6f_post_readiness_planning=true`;
- `allowed_for_live=false`;
- `order_endpoint_called=false`;
- `order_payload_generated=false`;
- `order_payload_sent=false`;
- `live_order_once_called=false`;
- `post_allowed_this_step=false`;
- `post_attempt_limit=1`;
- `post_executed=false`;
- retry/loop/add/change/cancel/close all false.

## Real API execution boundary

Step 6E is the first phase that may represent real read-only/preflight evidence,
but actual execution is allowed only when all gating inputs are safe. If it is
weekend, market closed, market-hours unknown, broker maintenance is suspected,
or a safe read-only/preflight route cannot be verified, the real API check must
not run.

For this implementation pass, the real API preflight was not executed because
the work date was Sunday JST. The model, tests, and docs were completed with
fake/sanitized inputs only.

## Step 6E-S Sunday offline preparation

Step 6E-S confirmed the Sunday blocker and added a market-open retry runbook
without calling any API. The retry is documented in
[STEP6E_R_MARKET_OPEN_RETRY_RUNBOOK.md](STEP6E_R_MARKET_OPEN_RETRY_RUNBOOK.md).

The next executable preflight attempt is Step 6E-R, and it must be requested as
a separate market-hours task. Step 6E-R is still read-only/preflight only,
no POST, no order endpoint, no `live_order_once`, no raw request/response
display or save, no headers/signatures/credentials/real IDs display, and
`allowed_for_live=false`.

Step 6F must not start until a fresh Step 6E-R sanitized result exists and the
user explicitly requests Step 6F.

## Safe read-only route requirements

A route must be verified before use:

- no POST;
- no order endpoint;
- no `live_order_once`;
- no raw output;
- sanitized fields only;
- no credential, header, signature, or ID display.

If any boundary is unclear, Step 6E blocks before calling real API.

## Market-hours / weekend blocker

Weekend JST, market-closed state, market-hours unknown, broker maintenance, or
holiday/special close state is fail-closed. Step 6E must stop without real API
execution in those states.

## Sanitized result fields

The ready result expects USD/JPY, zero open positions, zero active orders,
instrument minimum order size at or below 100, size step 1, spread at or below
0.01 JPY, ticker age at or below 30 seconds, permission/IP checks passed, and
previous result unknown false.

## Raw response / headers / signature policy

- `raw_request_saved=false`
- `raw_request_displayed=false`
- `raw_response_saved=false`
- `raw_response_displayed=false`
- `headers_saved=false`
- `headers_displayed=false`
- `signature_saved=false`
- `signature_displayed=false`
- credentials and real IDs displayed false

Only sanitized extracted fields may be reported.

## Ready preflight meaning

Ready means the sanitized preflight evidence passed Step 6E checks and can be
handed to a separate Step 6F post-readiness planning request. It is not live
POST permission and not approval to place an order.

## Blocked request meaning

`BLOCKED_STEP6E_PREFLIGHT_REQUEST` means the explicit Step 6E request or one or
more operator acknowledgements are missing.

## Blocked environment meaning

`BLOCKED_STEP6E_PREFLIGHT_ENVIRONMENT` means local repo/test/ruff/secret status,
market prefilter, safe-route verification, or env/raw-output safety is not safe.

## Blocked source plan meaning

`BLOCKED_STEP6E_SOURCE_PLAN` means the Step 6D plan is missing, blocked, not
ready, or unsafe.

## Blocked preflight result meaning

`BLOCKED_STEP6E_REAL_API_PREFLIGHT_RESULT` means a sanitized result was present
but failed account, positions, orders, instrument, ticker, permission,
market-hours, previous-result, raw exposure, or ID exposure checks.

## Future Step 6F handoff

Step 6F must be a separate explicit request. It remains no POST unless
separately scoped. Step 6E evidence must still be fresh, market-hours must be
rechecked, positions and active orders must remain zero, spread and ticker age
must stay within limits, and raw responses must remain undisplayed and unsaved.

One-shot POST remains Step 6G or later.

## Safety defaults

- `allowed_for_live=false`;
- `post_allowed_this_step=false`;
- `post_attempt_limit=1`;
- `post_executed=false`;
- `order_endpoint_called=false`;
- `order_payload_generated=false`;
- `order_payload_sent=false`;
- `live_order_once_called=false`;
- retry/loop/add/change/cancel/close all false;
- raw request/response/header/signature display and save flags false.

## Markdown rendering

The renderer includes explicit warnings that Step 6E is read-only/preflight
only, does not authorize live POST, keeps `allowed_for_live=false`, does not
call order endpoints, does not execute HTTP POST, does not call
`live_order_once`, and does not display raw request/response, headers,
signatures, credentials, or real IDs.

## Do-not-cross boundaries

Do not connect Step 6E to order endpoints, order payload generation,
`live_order_once`, speed/close/cancel/change paths, ledger operations, approval
command display/copying, raw response persistence, or HTTP POST.

## Tests

Tests cover ready sanitized preflight, request blocks, environment blocks,
source plan blocks, sanitized result failures, unsafe mismatch flags, future
Step 6F handoff/blockers, Markdown warnings, serialization safety, and
no-order/no-API import boundaries.

## Handoff summary

Step 6E is implemented as a read-only/preflight-only sanitized result model.
Actual real API preflight was not executed in this pass because Sunday JST is a
market blocker. Step 6E-S added the Step 6E-R market-open retry runbook without
API execution. Next work is an explicit Step 6E-R market-open retry request;
Step 6F remains blocked until a fresh safe Step 6E-R preflight exists and a
separate Step 6F request is made.

## Step 6E-RR route review result

Step 6E-R later stopped before API execution because no single verified safe
read-only/preflight route covered every required sanitized field. Step 6E-RR
reviewed route candidates offline and concluded that safe route consolidation
is needed before Step 6E-R2. Step 6E-RR did not call real API, read-only API,
public API, Private API, broker code, order endpoints, or `live_order_once`;
it did not execute POST and keeps `allowed_for_live=false`.

## Step 6E-SC consolidation result

Step 6E-SC adds the no-API/no-POST consolidation model that combines sanitized
private read-only, public market, and local/static inputs into one sanitized
Step 6E result. A ready consolidation is eligible only for Step 6E-R2 retry. It
does not execute API calls, does not call order endpoints or `live_order_once`,
does not execute POST, and does not make Step 6F eligible by itself.
