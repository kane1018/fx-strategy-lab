# Step 6G-PC-OX-E-B Operator-Executed Execution Boundary

## Summary

Step 6G-PC-OX-E-B adds the operator-executed execution boundary
formalization after the Step 6G-PC-X-P-R CASE 2 planning review.

This is skeleton-only. It defines the boundary between future actual checker
execution outside Codex and the safe boolean/category handoff that Codex may
consume. It is not checker execution.

## Scope

- Adds
  `backend/app/live_verification/live_order_real_operator_executed_execution_boundary.py`.
- Adds a pure skeleton status:
  `OPERATOR_EXECUTED_EXECUTION_BOUNDARY_READY_NO_ENV_NO_CHECK`.
- Keeps actual checker execution outside Codex.
- Allows Codex to receive only safe boolean/category handoff metadata.
- Requires the checker execution implementation skeleton, checker execution
  contract skeleton, operator checker workflow, and operator result handoff to
  be ready.

## Non-Execution Boundary

This boundary does not:

- access env or `.env`
- use `os.environ`, `getenv`, or dotenv
- perform an actual environment presence check
- execute the checker
- read credentials
- handle credential values
- handle credential metadata values
- save or display checker result detail
- save or display operator result detail
- save or display raw operator result values
- save or display sentinel values
- expose env variable names
- generate real signatures
- generate real header values
- call public API, read-only API, Private API, broker, or order endpoints
- call `live_order_once`
- execute HTTP POST
- change ledgers

## Ready Defaults

Ready means the execution boundary is declared, not executed.

- `boundary_mode=OPERATOR_EXECUTED_EXECUTION_BOUNDARY_SKELETON_ONLY`
- `boundary_declared=true`
- `operator_execution_boundary_declared=true`
- `operator_execution_must_be_outside_codex=true`
- `codex_execution_forbidden=true`
- `checker_execution_implementation_skeleton_ready=true`
- `checker_execution_contract_ready=true`
- `operator_result_handoff_safe=true`
- `operator_checker_workflow_ready=true`
- `operator_execution_performed=false`
- `codex_execution_performed=false`
- `env_access_requested=false`
- `codex_env_access_requested=false`
- `actual_environment_presence_check_performed=false`
- `credential_read_performed=false`
- `credential_values_present=false`
- `credential_metadata_present=false`
- `operator_result_provided=false`
- `operator_result_safe_boolean_category_only=true`
- `operator_result_detail_present=false`
- `operator_result_raw_value_present=false`
- `operator_result_unknown=false`
- `operator_result_failed=false`
- `operator_result_unavailable=false`
- `operator_result_stale=false`
- `operator_result_timeout=false`
- `operator_result_reused=false`
- `operator_result_previous_turn=false`
- `checker_result_detail_present=false`
- `env_variable_names_present=false`
- `sentinel_value_present=false`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`

## Stop Conditions

The skeleton blocks if any of the following are not safely declared:

- unsupported boundary mode
- missing boundary declaration
- missing operator execution boundary declaration
- missing outside-Codex requirement
- Codex execution is not forbidden
- missing checker execution implementation skeleton readiness
- missing checker execution contract readiness
- unsafe operator result handoff
- missing operator checker workflow readiness
- operator execution is performed in this Step
- Codex execution is performed
- env access is requested
- Codex env access is requested
- actual environment presence check is performed
- credential read is performed
- credential values or metadata are present
- operator result is provided before a future actual execution Step
- operator result is not safe boolean/category only
- operator result detail or raw operator result value is present
- operator result is unknown, failed, unavailable, stale, or timeout
- operator result is reused or previous-turn
- operator result is saved, displayed, or broadly propagated
- checker result detail is present
- env variable names are present
- sentinel values are present
- real signature, real headers, API, endpoint, `live_order_once`, or POST
  capability appears
- `post_allowed_this_step=true` or `post_executed=true`
- render/serialization is not safe
- retry or loop is enabled

Unknown / failed / unavailable / stale / timeout results always block POST.

## Internal Wiring

Step 6G-IW now includes a minimal
`operator_executed_execution_boundary_ready` gate. The gate only checks the
boundary contract and does not execute the checker.

Ready IW keeps:

- `operator_execution_must_be_outside_codex=true`
- `codex_execution_forbidden=true`
- `operator_execution_performed=false`
- `codex_execution_performed=false`
- `env_access_requested=false`
- `actual_environment_presence_check_performed=false`
- `operator_result_handoff_safe=true`
- `operator_result_raw_value_present=false`
- `operator_result_unknown=false`
- `operator_result_failed=false`
- `operator_result_unavailable=false`
- `operator_result_stale=false`
- `operator_result_timeout=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Future Work

Future actual checker execution is a separate Step. Future env access, real
credential injection, real signing, and real transport are also separate Steps.

Any future real execution requires a new final confirmation and fresh preflight.
Past final confirmation phrases are invalid for future execution.

Retry, loop, additional order, change order, cancel order, close order, raw
request/response exposure, secret exposure, real ID exposure, and approval
command exposure remain forbidden.
