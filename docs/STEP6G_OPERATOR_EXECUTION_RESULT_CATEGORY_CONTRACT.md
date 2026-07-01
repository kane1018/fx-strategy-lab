# Step 6G-PC-OX-R-C Operator Execution Result Category Contract

## Summary

Step 6G-PC-OX-R-C adds the operator-side execution result category contract
after the Step 6G-PC-OX-E-B-V CASE 2 boundary review.

This is category-only. It defines safe category labels for a future
operator-side checker execution result handoff to Codex. It is not checker
execution and does not receive an actual operator result in this Step.

## Scope

- Adds
  `backend/app/live_verification/live_order_real_operator_execution_result_category_contract.py`.
- Adds a pure category contract mode:
  `OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY`.
- Allows Codex to receive only safe category labels.
- Keeps actual checker execution outside Codex.
- Keeps the operator-executed execution boundary, operator result handoff, and
  operator checker workflow prerequisites fail-closed.

## Safe Category Set

Allowed safe labels:

- `NOT_PROVIDED`
- `READY_CONFIRMED`
- `BLOCKED_UNKNOWN`
- `BLOCKED_FAILED`
- `BLOCKED_UNAVAILABLE`
- `BLOCKED_STALE`
- `BLOCKED_TIMEOUT`
- `BLOCKED_REUSED`
- `BLOCKED_PREVIOUS_TURN`
- `BLOCKED_UNSAFE_DETAIL`
- `BLOCKED_UNSUPPORTED`

`READY_CONFIRMED` means only that the operator-side result category is a ready
category. It is not POST permission.

`NOT_PROVIDED` is the initial contract-ready state. It is not actual result
receipt.

All `BLOCKED_*` labels are fail-closed and do not permit POST.

## Non-Execution Boundary

This category contract does not:

- access env or `.env`
- use `os.environ`, `getenv`, or dotenv
- perform an actual environment presence check
- execute the checker
- receive actual operator result details
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

Ready with no result means the category contract is declared, not executed.

- `category_contract_mode=OPERATOR_EXECUTION_RESULT_CATEGORY_CONTRACT_ONLY`
- `category_contract_declared=true`
- `allowed_category_set_declared=true`
- `operator_executed_execution_boundary_ready=true`
- `operator_result_handoff_safe=true`
- `operator_checker_workflow_ready=true`
- `operator_result_category=NOT_PROVIDED`
- `operator_result_category_is_safe_label=true`
- `operator_result_category_is_allowed=true`
- `operator_result_provided=false`
- `operator_result_ready_confirmed=false`
- `operator_result_blocked=false`
- `actual_execution_performed=false`
- `codex_execution_performed=false`
- `env_access_requested=false`
- `credential_read_performed=false`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`

Ready confirmed keeps the same no-execution and no-POST constraints:

- `operator_result_category=READY_CONFIRMED`
- `operator_result_provided=true`
- `operator_result_ready_confirmed=true`
- `post_allowed_this_step=false`
- `post_executed=false`

## Stop Conditions

The contract blocks if any of the following are present:

- unsupported category contract mode
- missing category contract declaration
- missing allowed category set declaration
- missing operator-executed execution boundary readiness
- unsafe operator result handoff
- missing operator checker workflow readiness
- unsupported raw category label
- category not marked safe or not allowed
- `READY_CONFIRMED` without safe ready/provided semantics
- `NOT_PROVIDED` marked as provided, ready, or blocked
- unknown, failed, unavailable, stale, timeout category or flag
- reused or previous-turn category or flag
- operator result detail or raw operator result value
- operator result saved, displayed, or broadly propagated
- checker result detail
- env variable names
- credential values or metadata
- sentinel values
- actual execution or Codex execution
- env access or credential read
- real signature, real headers, API, endpoint, `live_order_once`, or POST
  capability
- `post_allowed_this_step=true` or `post_executed=true`
- unsafe render or serialization

Unknown / failed / unavailable / stale / timeout / reused / previous-turn
categories always block POST.

## Internal Wiring

Step 6G-IW now includes a minimal
`operator_execution_result_category_contract_ready` gate. The gate checks the
category contract and does not execute the checker or receive raw results.

Ready IW keeps:

- `operator_execution_result_category_contract_ready=true`
- `operator_result_category=NOT_PROVIDED` by default
- `operator_result_category_is_safe_label=true`
- `operator_result_category_is_allowed=true`
- `operator_result_detail_present=false`
- `operator_result_raw_value_present=false`
- `actual_execution_performed=false`
- `env_access_requested=false`
- `credential_read_performed=false`
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
