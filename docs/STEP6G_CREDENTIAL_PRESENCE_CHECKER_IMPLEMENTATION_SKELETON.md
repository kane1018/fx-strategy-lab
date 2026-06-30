# Step 6G Credential Presence Checker Implementation Skeleton

## Scope

Step 6G-PC-I-S follows the Step 6G-PC-OX-V boundary review. It adds a real
credential presence checker implementation skeleton for the future checker
interface, lifecycle, and stop conditions.

This Step is skeleton-only. It is not checker execution. It does not access
env or `.env`, does not use `os.environ` or `getenv`, and does not perform an
actual environment presence check.

This skeleton does not read credential values, credential metadata, env
variable names, sentinel text, checker result detail, or operator result
detail. It preserves the operator-executed checker workflow boundary. It does
not generate real signatures or real header values. It does not execute API
calls, HTTP POST, order endpoint calls, or `live_order_once`.

## Implementation Contract

The ready mode is `CHECKER_IMPLEMENTATION_SKELETON_ONLY`.

The ready status is
`CREDENTIAL_PRESENCE_CHECKER_IMPLEMENTATION_READY_NO_ENV_NO_CHECK`.

Ready requires:

- checker contract ready
- operator checker workflow ready
- credential presence adapter ready
- credential presence check ready
- implementation interface declared
- implementation lifecycle declared
- execution deferred to a future Step
- no checker execution
- no Codex env access request
- no actual environment presence check
- no env access capability
- no credential read capability
- no credential values or credential metadata
- no checker result availability or detail
- checker result not unknown, failed, unavailable, or stale
- checker result not saved or displayed
- operator-executed workflow supported and preserved
- no real signature, real headers, or HTTP POST capability

## Safety Defaults

Ready still means:

- `checker_implementation_skeleton_ready=true`
- `checker_contract_ready=true`
- `operator_checker_workflow_ready=true`
- `execution_deferred_to_future_step=true`
- `execution_performed=false`
- `codex_env_access_requested=false`
- `actual_environment_presence_check_performed=false`
- `env_access_capability_present=false`
- `credential_read_capability_present=false`
- `credential_values_read=false`
- `credential_values_present=false`
- `credential_metadata_present=false`
- `checker_result_available=false`
- `checker_result_unknown=false`
- `checker_result_failed=false`
- `checker_result_unavailable=false`
- `checker_result_stale=false`
- `operator_workflow_supported=true`
- `operator_workflow_preserved=true`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Blocks

The skeleton blocks:

- wrong implementation mode
- missing checker contract / operator workflow / adapter / check readiness
- missing implementation interface or lifecycle declaration
- execution not deferred to a future Step
- checker execution
- Codex env access request
- actual environment presence check
- env access capability
- credential read capability
- credential value or credential metadata exposure
- checker result availability, detail, save, or display
- unknown, failed, unavailable, or stale checker result
- loss of operator-executed workflow support or preservation
- real signing, real headers, HTTP POST, order endpoint, or `live_order_once`
- unsafe render or serialization settings

Unknown, failed, unavailable, and stale checker result states always block.
They never permit POST.

## Internal Wiring

Step 6G-IW now requires `checker_implementation_skeleton_ready=true` after
`operator_checker_workflow_ready=true`.

The internal wiring keeps only sanitized skeleton flags. It does not store or
render checker result detail, operator result detail, credential values,
credential metadata, env variable names, sentinel text, raw request, raw
response, or real IDs.

Ready internal wiring still keeps:

- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Non-Goals

This Step does not implement:

- checker execution
- Codex env access
- actual environment presence check
- real credential injection
- real credential handle creation
- real signing value generation
- real header value generation
- real HTTP transport
- real order endpoint call
- live order execution

Future checker execution is a separate Step. Future real credential injection,
real signing, and real transport must remain separate Steps.

Future real execution requires a new final confirmation and fresh preflight.

Retry, loop, add order, change order, cancel order, and close order remain
forbidden. Raw/secret/ID exposure remains forbidden.
