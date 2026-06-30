# Step 6G-PC-X-C Credential Presence Checker Execution Contract

## Summary

Step 6G-PC-X-C adds the checker execution contract skeleton after the
Step 6G-PC-X-R CASE 2 planning review.

This is skeleton-only. It defines future checker execution inputs, outputs, and
stop conditions, but it does not execute the checker.

## Scope

- Adds
  `backend/app/live_verification/live_order_real_credential_presence_checker_execution_contract.py`.
- Adds a pure contract status:
  `CREDENTIAL_PRESENCE_CHECKER_EXECUTION_CONTRACT_READY_NO_ENV_NO_CHECK`.
- Keeps the operator-executed workflow boundary preserved.
- Allows only boolean/category metadata and safe status strings.

## Non-Execution Boundary

This contract does not:

- access env or `.env`
- use `os.environ`, `getenv`, or dotenv
- perform an actual environment presence check
- read credentials
- handle credential values
- handle credential metadata values
- save or display checker result detail
- save or display operator result detail
- generate real signatures
- generate real header values
- call public API, read-only API, Private API, broker, or order endpoints
- call `live_order_once`
- execute HTTP POST
- change ledgers

## Ready Defaults

Ready means the execution contract is declared, not executed.

- `execution_contract_mode=CHECKER_EXECUTION_CONTRACT_SKELETON_ONLY`
- `checker_implementation_skeleton_ready=true`
- `operator_checker_workflow_ready=true`
- `checker_contract_ready=true`
- `execution_contract_declared=true`
- `execution_inputs_declared=true`
- `execution_outputs_declared=true`
- `execution_stop_conditions_declared=true`
- `execution_deferred_to_future_step=true`
- `execution_performed=false`
- `execution_performed_by_codex=false`
- `execution_performed_by_operator=false`
- `codex_env_access_requested=false`
- `actual_environment_presence_check_performed=false`
- `credential_read_performed=false`
- `credential_values_present=false`
- `credential_metadata_present=false`
- `checker_result_available=false`
- `checker_result_detail_present=false`
- `checker_result_unknown=false`
- `checker_result_failed=false`
- `checker_result_unavailable=false`
- `checker_result_stale=false`
- `checker_result_timeout=false`
- `operator_workflow_preserved=true`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`

## Stop Conditions

The contract blocks if any of the following are not safely declared:

- unsupported execution contract mode
- missing checker implementation skeleton readiness
- missing operator checker workflow readiness
- missing checker contract readiness
- missing input/output/stop-condition declaration
- execution is not deferred
- checker execution is performed by Codex or operator
- Codex env access is requested
- actual environment presence check is performed
- credential read is performed
- credential values or metadata are present
- checker result is available, detailed, saved, displayed, or broadly propagated
- checker result is unknown, failed, unavailable, stale, or timeout
- operator workflow boundary is not preserved
- real signature, real headers, API, endpoint, `live_order_once`, or POST capability appears
- `post_allowed_this_step=true` or `post_executed=true`
- render/serialization is not safe
- retry or loop is enabled

Unknown / failed / unavailable / stale / timeout results always block POST.

## Internal Wiring

Step 6G-IW now includes a minimal `checker_execution_contract_ready` gate.
The gate only checks the contract skeleton and does not execute the checker.

Ready IW still keeps:

- `execution_performed=false`
- `execution_performed_by_codex=false`
- `execution_performed_by_operator=false`
- `codex_env_access_requested=false`
- `actual_environment_presence_check_performed=false`
- `credential_read_performed=false`
- `checker_result_available=false`
- `checker_result_timeout=false`
- `operator_workflow_preserved=true`
- `post_allowed_this_step=false`
- `post_executed=false`

## Future Work

Future checker execution is a separate Step. Future real credential injection,
real signing, and real transport are also separate Steps.

Any future real execution requires a new final confirmation and fresh preflight.
Past final confirmation phrases are invalid for future execution.

Retry, loop, additional order, change order, cancel order, close order, raw
request/response exposure, secret exposure, real ID exposure, and approval
command exposure remain forbidden.
