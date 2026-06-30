# Step 6G Operator-Executed Checker Workflow

## Scope

Step 6G-PC-OX follows the Step 6G-PC-I-R planning review. It adds an
operator-executed checker workflow skeleton for credential presence readiness.
Step 6G-PC-OX-H hardens that workflow result handoff after the Step
6G-PC-X-C-V boundary review. The handoff remains skeleton-only and safe
boolean/category only.

The operator performs any credential presence confirmation outside Codex.
Codex receives only safe boolean/category metadata. Codex does not read env or
`.env`, does not use `os.environ` or `getenv`, and does not perform an actual
environment presence check.

This workflow is skeleton-only. It is not a real checker implementation and it
does not execute a checker. It does not use credential values, credential
metadata, env variable names, sentinel text, or operator checker result
details. It does not generate real signatures or real header values. It does
not execute API calls, HTTP POST, order endpoint calls, or `live_order_once`.

Step 6G-PC-OX-H adds explicit handoff safety gates. Raw operator result values,
operator result details, credential metadata, env variable names, sentinel
values, previous-turn results, reused results, stale results, unknown results,
failed results, unavailable results, and timeout results are all blocked. The
workflow does not store or render raw operator result values, and it does not
reuse previous operator results or previous-turn sentinels.

## Workflow Contract

The ready mode is `OPERATOR_EXECUTED_CHECKER_WORKFLOW_SKELETON_ONLY`.

The ready status is
`OPERATOR_CHECKER_WORKFLOW_READY_NO_CODEX_ENV_NO_API_NO_POST`.

Ready requires:

- credential presence checker contract ready
- credential presence adapter ready
- credential presence check ready
- operator workflow declared
- operator execution required
- operator execution performed outside Codex
- no Codex checker execution
- no Codex env access request
- no actual environment presence check performed by Codex
- operator result handoff declared
- operator result handoff safe
- operator result category-only
- operator result provided as boolean/category metadata only
- no raw operator result value present, saved, or displayed
- operator result fresh
- operator result not stale, reused, or previous-turn
- operator result not unknown, failed, unavailable, or timeout
- operator result not saved, displayed, or broadly propagated
- no operator result detail
- no credential values or credential metadata
- no env variable names
- no sentinel value
- no checker result detail
- no real signature, real headers, or HTTP POST capability

## Safety Defaults

Ready still means:

- `operator_checker_workflow_ready=true`
- `operator_execution_performed_outside_codex=true`
- `codex_execution_performed=false`
- `codex_env_access_requested=false`
- `actual_environment_presence_check_performed_by_codex=false`
- `operator_result_handoff_declared=true`
- `operator_result_handoff_safe=true`
- `operator_result_category_only=true`
- `operator_result_provided=true`
- `operator_result_is_boolean_only=true`
- `operator_result_raw_value_present=false`
- `operator_result_raw_value_saved=false`
- `operator_result_raw_value_displayed=false`
- `operator_result_fresh=true`
- `operator_result_stale=false`
- `operator_result_reused=false`
- `operator_result_previous_turn=false`
- `operator_result_timeout=false`
- `operator_result_unknown=false`
- `operator_result_failed=false`
- `operator_result_unavailable=false`
- `operator_result_saved=false`
- `operator_result_displayed=false`
- `credential_values_present=false`
- `credential_metadata_present=false`
- `env_variable_names_present=false`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Blocks

The workflow blocks:

- wrong workflow mode
- missing credential presence checker contract / adapter / check readiness
- missing operator workflow declaration
- missing operator execution requirement
- operator execution not performed outside Codex
- Codex checker execution
- Codex env access request
- actual environment presence check performed by Codex
- operator result handoff not declared
- unsafe operator result handoff
- missing operator result
- non-boolean/category operator result
- raw operator result value present, saved, or displayed
- stale, reused, or previous-turn operator result
- unknown, failed, unavailable, or timeout operator result
- operator result saved, displayed, broadly propagated, or detailed
- credential value or credential metadata exposure
- env variable name exposure
- sentinel value exposure
- checker result detail exposure
- real signing, real headers, HTTP POST, order endpoint, or `live_order_once`
- unsafe render or serialization settings

Unknown, failed, unavailable, stale, reused, previous-turn, and timeout results
always block. They never permit POST.

## Internal Wiring

Step 6G-IW now requires `operator_checker_workflow_ready=true` after
`credential_presence_checker_contract_ready=true`.

The internal wiring keeps only sanitized workflow flags. It does not store or
render operator result details, credential values, credential metadata, env
variable names, sentinel text, checker result details, raw request, raw
response, or real IDs.

Step 6G-PC-OX-H also carries the safe handoff flags into internal wiring:
`operator_result_handoff_safe=true`, `operator_result_raw_value_present=false`,
`operator_result_previous_turn=false`, `operator_result_reused=false`, and
`operator_result_timeout=false`. Unsafe raw value, previous-turn, reused,
timeout, detail, env-name, credential metadata, or POST flags fail closed.

Ready internal wiring still keeps:

- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Non-Goals

This Step does not implement:

- real credential presence checker implementation
- real checker execution
- Codex env access
- actual environment presence check inside Codex
- real credential injection
- real credential handle creation
- real signing value generation
- real header value generation
- real HTTP transport
- real order endpoint call
- live order execution

Future real checker implementation is a separate Step. Future real checker
execution is also a separate Step. Future real credential injection, real
signing, and real transport must remain separate Steps.

Future real execution requires a new final confirmation and fresh preflight.

Retry, loop, add order, change order, cancel order, and close order remain
forbidden. Raw/secret/ID exposure remains forbidden.
