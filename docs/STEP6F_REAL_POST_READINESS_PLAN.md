# Step 6F Real Post Readiness Plan

## Summary

Step 6F adds a planning-only post-readiness model after a sanitized Step 6E-R2
preflight pass. It accepts the Step 6E-R2 result as sanitized input and decides
whether the project can wait for a separate explicit Step 6G one-shot POST
request.

Step 6F is not live execution. Ready Step 6F output keeps
`allowed_for_live=false`, `post_allowed_this_step=false`, and
`post_executed=false`.

## Scope

This step adds:

- `LiveOrderRealPostReadinessPreflightSnapshot`;
- `LiveOrderRealPostReadinessRequestSnapshot`;
- `LiveOrderRealPostReadinessPlan`;
- `LiveOrderRealPostReadinessGoNoGoReport`;
- check results, fail-closed statuses, and sanitized Markdown rendering.

The Step 6E-R2 runtime result is not committed to Git. Step 6F receives it as a
sanitized snapshot.

## What this step does

- Records that Step 6F was explicitly requested.
- Records operator acknowledgements for real-money risk and planning-only
  scope.
- Checks that the source Step 6E-R2 preflight was executed, passed, consolidated,
  and eligible for Step 6F.
- Checks freshness with `preflight_result_max_age_seconds=60` by default.
- Checks market, position/order, instrument, ticker, permission, IP/account, and
  previous-result conditions.
- Checks raw/header/signature/credential/ID non-exposure flags.
- Defines go/no-go/stop conditions before any future Step 6G request.
- Defines future Step 6G handoff conditions and blockers.

## What this step does not do

- Step 6F is planning-only.
- Step 6F is no POST.
- Step 6F does not call an order endpoint.
- Step 6F does not generate an order payload.
- Step 6F does not send an order payload.
- Step 6F does not call `live_order_once`.
- Step 6F does not call broker order paths.
- Step 6F does not call real API, read-only API, public API, or Private API.
- Step 6F does not display or save raw request, raw response, headers,
  signatures, credentials, or real IDs.
- Step 6F does not display, copy, or persist a full approval command.
- Step 6F does not set `allowed_for_live=true`.

## Input: Step 6E-R2 sanitized preflight snapshot

`LiveOrderRealPostReadinessPreflightSnapshot` contains only sanitized fields:

- source Step 6E-R2 status and pass flags;
- source Step 6E-SC consolidation status and ready flag;
- market session/window/maintenance/holiday/unknown flags;
- account asset status, open positions count, active orders count;
- instrument symbol, minimum order size, size step, rule pass flag;
- ticker symbol, spread, age, and pass flag;
- permission scope, IP/account binding, previous-result-unknown checks;
- raw/header/signature/credential/ID non-exposure flags;
- preflight age and max age.

Ready Step 6F requires `source_execution_status=REAL_API_PREFLIGHT_PASSED_NO_POST`,
`source_api_preflight_executed=true`, `source_api_preflight_passed=true`,
`source_consolidation_ready=true`, and
`source_eligible_for_step6f_post_readiness_planning=true`.

## Input: Step 6F request snapshot

`LiveOrderRealPostReadinessRequestSnapshot` requires:

- explicit Step 6F user instruction received;
- real-money risk understood;
- no POST in Step 6F understood;
- no order endpoint in Step 6F understood;
- no `live_order_once` in Step 6F understood;
- post-readiness planning-only scope understood;
- Step 6G required for any one-shot POST understood;
- fresh preflight required before Step 6G understood;
- unknown means stop understood;
- scope label
  `post_readiness_planning_only_no_post_no_order_endpoint_no_live_order_once`.

## Output: LiveOrderRealPostReadinessPlan

Ready output uses:

- `plan_status=POST_READINESS_PLANNED_NO_POST`;
- `plan_ready=true`;
- `eligible_for_step6g_one_shot_post_request=true`;
- `allowed_for_live=false`;
- `post_readiness_planned=true`;
- `post_authorized_this_step=false`;
- `post_allowed_this_step=false`;
- `post_attempt_limit=1`;
- `post_executed=false`;
- `order_endpoint_called=false`;
- `order_payload_generated=false`;
- `order_payload_sent=false`;
- `live_order_once_called=false`;
- `broker_order_path_called=false`;
- retry/loop/add/change/cancel/close all false.

## Post-readiness meaning

Post-readiness means the sanitized Step 6E-R2 preflight pass was fresh enough to
plan the next handoff. It only allows the operator to stop and wait for a
separate explicit Step 6G request. It is not live POST authorization.

## Why this is not POST authorization

Step 6F never transitions to `allowed_for_live=true`, never authorizes POST, and
never calls order routes. It also requires Step 6G to recheck fresh preflight
immediately before any controlled one-shot POST decision.

## Freshness policy

The default freshness limit is `preflight_result_max_age_seconds=60`. If
`preflight_result_age_seconds` is greater than that value, Step 6F returns
`BLOCKED_STEP6F_PREFLIGHT_STALE`.

Step 6F does not rely on stale Step 6E-R2 evidence.

## Required rechecks before Step 6G

Before Step 6G, the following must be rechecked or refreshed:

- fresh real API preflight;
- approval artifact validation;
- market-hours state;
- open positions and active orders;
- ticker spread and age.

## Go conditions

- explicit Step 6G request required;
- Step 6E-R2 preflight must be fresh or rerun;
- market-hours must be rechecked immediately before Step 6G;
- open positions and active orders must remain zero;
- ticker spread and age must remain within limits;
- approval artifact must be revalidated or confirmed fresh;
- post attempt limit remains 1;
- no retry / no loop / no add / no change / no cancel / no close.

## No-go conditions

- no explicit Step 6G request;
- stale preflight;
- market closed or unknown;
- open position exists;
- active order exists;
- spread too wide;
- ticker stale;
- permission/IP/account binding failed;
- raw response exposure risk;
- any order endpoint called before Step 6G;
- any need for retry/loop/add/change/cancel/close.

## Stop conditions

- unknown status;
- result_unknown;
- stale or missing fresh preflight;
- approval artifact validation stale;
- exact match cannot be guaranteed;
- raw/secret/ID exposure risk;
- post attempt would exceed 1;
- any unexpected API response shape;
- any previous step inconsistency.

## Future Step 6G handoff

Step 6G requires:

- user explicitly requests Step 6G one-shot POST;
- fresh real API preflight rerun immediately before POST;
- approval artifact validation refreshed or confirmed;
- exact one-line approval command still valid;
- `allowed_for_live` remains false until Step 6G controlled transition;
- Step 6G must still stop before POST if any uncertainty;
- Step 6G must attempt at most one POST.

## Safety defaults

- `allowed_for_live=false`;
- `post_authorized_this_step=false`;
- `post_allowed_this_step=false`;
- `post_attempt_limit=1`;
- `post_executed=false`;
- `order_endpoint_called=false`;
- `order_payload_generated=false`;
- `order_payload_sent=false`;
- `live_order_once_called=false`;
- `broker_order_path_called=false`;
- `retry_allowed=false`;
- `loop_allowed=false`;
- `add_order_allowed=false`;
- `change_order_allowed=false`;
- `cancel_order_allowed=false`;
- `close_order_allowed=false`.

## Markdown rendering

The renderer displays only sanitized plan fields, go/no-go/stop/handoff lists,
check results, blocked reasons, and the recommended next step.

The renderer includes these warnings:

- This Step 6F post-readiness plan is planning-only.
- This Step 6F plan does not authorize live POST.
- This Step 6F plan keeps allowed_for_live=false.
- This Step 6F plan does not call any order endpoint.
- This Step 6F plan does not generate or send an order payload.
- This Step 6F plan does not call live_order_once.
- This Step 6F plan does not execute HTTP POST.
- Step 6G requires a separate explicit request and fresh preflight.

It does not render API keys, secrets, raw request, raw response, headers,
signatures, order IDs, execution IDs, position IDs, client order IDs, or a full
approval command.

## Do-not-cross boundaries

Do not connect Step 6F to API clients, brokers, order endpoints,
`live_order_once`, ledgers, `.env`, credential reads, raw request/response
storage, clipboard, shell command rendering, or Step 6G execution.

## Tests

Tests cover ready planning, request blockers, preflight-not-ready blockers,
stale blockers, preflight-not-passing blockers, unsafe state blockers, Step 6G
condition presence, Markdown warnings, serialization safety, and no-order import
boundaries.

## Handoff summary

Step 6F is complete when it can produce a planning-only
`POST_READINESS_PLANNED_NO_POST` result from a fresh sanitized Step 6E-R2 pass.
After Step 6F, stop and wait for a separate explicit Step 6G request. Step 6G
must refresh preflight immediately before any one-shot POST decision.
