# Step 6G Credential Presence Adapter Skeleton

## Scope

Step 6G-PC-A follows the Step 6G-PC-V boundary review. It adds a credential
presence adapter skeleton that passes an operator-provided presence result into
an adapter boundary as safe boolean/category metadata only.

This is not a real checker. It does not perform an actual environment presence
check. It does not read env or `.env`. It does not use credential values,
credential metadata, or sentinel text. It does not generate real signatures or
real header values. It does not execute API calls, HTTP POST, order endpoint
calls, or `live_order_once`.

## Contract

The ready mode is `PRESENCE_ADAPTER_SKELETON_ONLY`.

The ready status is `CREDENTIAL_PRESENCE_ADAPTER_READY_NO_ENV_NO_REAL_CHECK`.

Ready requires:

- credential presence check ready
- credential boundary ready
- credential handle ready
- credential injection ready
- operator-provided presence result
- operator presence result is boolean-only
- operator presence result is fresh
- operator presence result is not reused
- operator presence result is not stale
- operator presence result is not from a previous turn
- presence result adapted
- presence result not saved, displayed, or broadly propagated
- sentinel value/hash/fingerprint/length are not present, displayed, or saved
- credential values and credential metadata are not present
- no actual environment presence check
- no env, `.env`, or printenv access
- no real checker attached or executed
- no real signing, real headers, or HTTP POST capability

## Safety Defaults

Ready still means:

- `actual_environment_presence_check_performed=false`
- `env_access_requested=false`
- `real_checker_attached=false`
- `real_checker_executed=false`
- `sentinel_value_present=false`
- `credential_values_present=false`
- `credential_metadata_present=false`
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

- wrong adapter mode
- missing credential presence check / boundary / handle / injection prerequisites
- missing or non-boolean operator presence result
- stale, reused, or previous-turn operator presence result
- missing adapter conversion
- sentinel value/hash/fingerprint/length exposure
- credential value or metadata presence
- actual environment presence check
- env / `.env` / printenv access
- real checker attachment or execution
- broad propagation, display, or saving of the presence result
- real signing, real headers, or HTTP POST capability
- unsafe render / serialization settings

## Internal Wiring

Step 6G-IW now requires `credential_presence_adapter_ready=true` after
`credential_presence_check_ready=true`.

The internal wiring keeps only sanitized contract flags. It does not store or
render the operator sentinel text. It does not render or serialize credential
values, credential metadata, raw request, raw response, real IDs, or real checker
output.

## Non-Goals

This Step does not implement:

- real credential presence check
- env access
- real checker attachment or execution
- real credential injection
- real credential handle creation
- real signing value generation
- real header value generation
- real HTTP transport
- real order endpoint call
- live order execution

Future real credential presence check, future real credential injection, future
real signing, and future real transport must be separate Steps. Future real
execution requires a new final confirmation and fresh preflight.

Retry, loop, add order, change order, cancel order, and close order remain
forbidden. Raw/secret/ID exposure remains forbidden.
