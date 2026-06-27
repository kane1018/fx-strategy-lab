# Step 6D Real API Preflight Plan

## Summary

Step 6D adds a dry-run planning model for future real API preflight execution.
It receives the validated Step 6C approval artifact and produces a sanitized
plan for what Step 6E or later must check before any live boundary can be
considered.

Step 6D is no API and no POST. It does not execute read-only API, public API,
Private API, broker code, `live_order_once`, market-hours API checks, ledger
reads, or order endpoints.

## Scope

Step 6D is limited to planning:

- confirm that Step 6C validation is ready and fresh;
- confirm an explicit Step 6D planning request and operator acknowledgements;
- define future API preflight checks for Step 6E or later;
- define raw request/response, header, and signature handling rules;
- define go/no-go/stop conditions before Step 6E;
- define handoff conditions and blockers for future Step 6E.

## What this step does

The Step 6D model creates `LiveOrderRealApiPreflightPlan` from:

- `LiveOrderRealApprovalArtifactValidation`;
- `LiveOrderRealApiPreflightPlanRequestSnapshot`;
- `LiveOrderRealApiPreflightPlanSafetySnapshot`;
- future planned check definitions;
- safe data handling policy.

Ready output uses
`API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST`, sets
`api_preflight_planned=true`, and keeps all execution flags off.

## What this step does not do

Step 6D does not:

- call read-only API;
- call public API;
- call Private API;
- connect to broker code;
- call `live_order_once`;
- execute real API preflight;
- execute HTTP POST;
- issue an approval gate;
- generate a new approval id;
- generate, display, copy, persist, or execute an approval command;
- read or write ledgers;
- read `.env` or environment values;
- save or display raw request/response, headers, or signatures.

## Input: LiveOrderRealApprovalArtifactValidation

The source validation must be Step 6C ready:

- `validation_status=APPROVAL_ARTIFACT_VALIDATED_NO_API_NO_POST`;
- `validation_ready=true`;
- `approval_artifact_validated=true`;
- `eligible_for_step6d_api_preflight_planning=true`;
- `approval_gate_enabled=true`;
- `allowed_for_live=false`;
- `approval_gate_issued=false`;
- `approval_command_copyable=false`;
- `approval_command_displayed=false`;
- `approval_command_persisted=false`;
- `approval_command_copied_to_clipboard=false`;
- `approval_command_executable=false`;
- API, broker, `live_order_once`, and POST flags all false.

`approval_gate_enabled=true` remains Step 6A state-only enablement evidence.
It is not live POST permission and not real approval gate issuance.

## Input: ApiPreflightPlanRequestSnapshot

The request snapshot records only sanitized acknowledgements:

- explicit Step 6D user instruction received;
- operator understands real-money risk;
- operator understands Step 6D is planning only;
- operator understands no API, no POST, and no `live_order_once` in Step 6D;
- operator understands Step 6E is still required for real API preflight;
- operator understands Step 6F or later is still required for POST;
- operator understands raw response is not saved or displayed;
- operator understands unknown means stop.

The request scope must be
`api_preflight_planning_only_no_real_api_no_post`.

## Input: ApiPreflightPlanSafetySnapshot

The safety snapshot is sanitized input only. It does not fetch current state.
It blocks stale validation, weekend/closed/maintenance/unknown market state,
unsafe raw handling, failed secret scan, dirty Git, failed tests, failed ruff,
unexpected API calls, unexpected broker calls, unexpected `live_order_once`, or
unexpected POST.

Defaults:

- `source_validation_max_age_seconds=300`;
- `timezone=Asia/Tokyo`;
- `market_hours_source=sanitized_snapshot_only`;
- `market_hours_snapshot_max_age_seconds=30`.

## Output: LiveOrderRealApiPreflightPlan

Ready output:

- `plan_status=API_PREFLIGHT_PLAN_READY_NO_REAL_API_NO_POST`;
- `plan_ready=true`;
- `eligible_for_step6e_real_api_preflight_execution=true`;
- `allowed_for_live=false`;
- `approval_gate_enabled=true`;
- `approval_artifact_validated=true`;
- `approval_gate_issued=false`;
- `approval_command_copyable=false`;
- `approval_command_displayed=false`;
- `approval_command_executable=false`;
- `api_preflight_planned=true`;
- `api_preflight_executed=false`;
- `real_api_execution_deferred_to_step6e=true`;
- API, broker, `live_order_once`, and POST flags all false;
- retry/loop/add/change/cancel/close flags false;
- `post_attempt_limit=1`.

## Planned API checks

Step 6D defines these future checks without executing them:

- `market_hours_and_session_check`;
- `account_asset_status_check`;
- `open_positions_count_check`;
- `active_orders_count_check`;
- `instrument_rule_check`;
- `ticker_spread_check`;
- `ticker_age_check`;
- `permission_scope_check`;
- `ip_account_binding_check`;
- `previous_result_unknown_check`;
- `raw_response_handling_check`.

Each planned check is for `Step 6E or later`, is classified as
`future_read_only_or_preflight_only`, requires read-only behavior, forbids POST,
extracts sanitized fields only, displays sanitized summary only, and stores no
raw data.

## Data handling policy

Step 6D fixes this policy:

- raw request saved/displayed: false;
- raw response saved/displayed: false;
- headers saved/displayed: false;
- signature saved/displayed: false;
- order/execution/position/client order IDs display allowed: false;
- credential display/storage allowed: false;
- sanitized fields only: true.

Allowed display fields are counts, spread, ticker age, market state, instrument
rules, permission/IP check booleans, and `result_unknown`.

## Raw response policy

Future Step 6E may extract only sanitized fields. Raw response, raw request,
headers, signatures, credentials, full URLs with credentials, order IDs,
execution IDs, position IDs, client order IDs, open price, and detailed P/L must
not be displayed or saved.

## Ready plan meaning

Ready means only that Step 6E real API preflight execution can be planned as a
separate explicit task. It does not authorize live POST, does not issue an
approval gate, does not create copyable approval text, and does not call any API.

## Blocked request meaning

`BLOCKED_STEP6D_API_PREFLIGHT_PLAN_REQUEST` means the explicit Step 6D request
or one or more required operator acknowledgements are missing or out of scope.

## Blocked safety snapshot meaning

`BLOCKED_STEP6D_API_PREFLIGHT_PLAN_SAFETY_SNAPSHOT` means the sanitized safety
snapshot is stale or unsafe, including market closed/unknown, maintenance,
weekend, raw exposure risk, failed tests/ruff/Git/secret scan, or unexpected
API/broker/POST activity.

## Blocked source validation meaning

`BLOCKED_STEP6D_SOURCE_VALIDATION` means Step 6C validation is missing, blocked,
not ready, or not eligible for Step 6D planning.

## Future Step 6E handoff

Step 6E must be a separate explicit request. It may execute real API preflight
only within its own scope and must remain no POST unless a later step explicitly
changes that boundary. Step 6E must report only sanitized extracted fields,
must not call order action endpoints, must not call `live_order_once`, and must
stop on unknown or unsafe state.

Step 6F or later remains the earliest place to consider one-shot POST, still
with separate approval, final dynamic preflight, one attempt, and no retry/loop.

## Safety defaults

- `allowed_for_live=false`;
- `api_preflight_planned=true` only in ready plans;
- `api_preflight_executed=false`;
- `real_api_execution_deferred_to_step6e=true` only in ready plans;
- `read_only_api_called=false`;
- `public_api_called=false`;
- `private_api_called=false`;
- `broker_called=false`;
- `live_order_once_called=false`;
- `post_allowed_this_step=false`;
- `post_attempt_limit=1`;
- `post_executed=false`;
- retry/loop/add/change/cancel/close all false.

## Markdown rendering

The renderer includes warnings that Step 6D is dry-run only, does not call
read-only/public/Private API, does not call broker code, does not call
`live_order_once`, does not execute HTTP POST, does not authorize live POST,
keeps `allowed_for_live=false`, and does not display or save raw request or
raw response.

## Do-not-cross boundaries

Do not connect Step 6D to API clients, broker code, `live_order_once`, ledgers,
clipboard, approval command files, approval gate issuance, or HTTP POST.

## Tests

Tests cover ready planning, missing request, missing acknowledgements, blocked
source validation, unsafe source flags, stale/unsafe safety snapshots, planned
check completeness, data handling policy, future Step 6E handoff, Markdown
warnings, serialization safety, and no-order/no-API import boundaries.

## Handoff summary

Step 6D is complete when the plan can be built from a ready Step 6C validation,
explicit Step 6D request, and safe sanitized snapshot, while all real API,
broker, `live_order_once`, approval command, ledger, and POST paths remain off.
Next work is a separate Step 6E real API preflight execution request.

## Step 6E Follow-up

Step 6E adds `LiveOrderRealApiPreflightExecution` as a read-only/preflight-only
sanitized result model. It can represent a passed real API preflight result as
`REAL_API_PREFLIGHT_PASSED_NO_POST`, but it still keeps
`allowed_for_live=false`, `post_allowed_this_step=false`,
`post_executed=false`, `order_endpoint_called=false`,
`order_payload_generated=false`, `order_payload_sent=false`, and
`live_order_once_called=false`.

Step 6E requires a safe read-only/preflight route, no raw request/response or
headers/signature exposure, and fail-closed market/weekend checks. In the
implementation pass, real API preflight was not executed because the work date
was Sunday JST. Details:
[STEP6E_REAL_API_PREFLIGHT_EXECUTION.md](STEP6E_REAL_API_PREFLIGHT_EXECUTION.md).
