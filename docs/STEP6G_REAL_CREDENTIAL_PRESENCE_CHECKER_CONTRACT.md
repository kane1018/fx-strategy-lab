# Step 6G Real Credential Presence Checker Contract

## Scope

Step 6G-PC-C follows the Step 6G-PC-A-V boundary review. It adds a real
credential presence checker contract for a future checker implementation.

This is contract-only. It is not a real checker. It does not perform an actual
environment presence check. It does not read env or `.env`. It does not use
credential values, credential metadata, sentinel text, or checker result
details. It does not generate real signatures or real header values. It does
not execute API calls, HTTP POST, order endpoint calls, or `live_order_once`.

## Contract

The ready mode is `CHECKER_CONTRACT_ONLY`.

The ready status is
`CREDENTIAL_PRESENCE_CHECKER_CONTRACT_READY_NO_ENV_NO_REAL_CHECK`.

Ready requires:

- credential presence adapter ready
- credential presence check ready
- credential boundary ready
- credential handle ready
- credential injection ready
- checker contract requested
- checker contract ready requested
- no real checker implementation present
- no real checker attached or executed
- no actual environment presence check performed
- env access required as a future fact, but not allowed in this Step
- no env, `.env`, or printenv access requested
- no credential values available, read, displayed, or saved
- no credential metadata available, displayed, or saved
- no checker result available, saved, displayed, or broadly propagated
- checker result contract remains boolean-only
- checker result is not unknown or failed
- no real signing, real headers, or HTTP POST capability

## Safety Defaults

Ready still means:

- `real_checker_implementation_present=false`
- `real_checker_attached=false`
- `real_checker_executed=false`
- `actual_environment_presence_check_performed=false`
- `env_access_allowed=false`
- `env_access_requested=false`
- `credential_values_available=false`
- `credential_values_read=false`
- `credential_metadata_available=false`
- `checker_result_available=false`
- `checker_result_saved=false`
- `checker_result_displayed=false`
- `checker_result_unknown=false`
- `checker_result_failed=false`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Blocks

The contract blocks:

- wrong checker contract mode
- missing credential presence adapter / presence check / boundary / handle /
  injection prerequisites
- missing checker contract request flags
- real checker implementation presence
- real checker attachment or execution
- actual environment presence check
- env access allowed or requested
- `.env` or printenv access requested
- credential value availability, read, display, or save
- credential metadata availability, display, or save
- checker result availability, save, display, or broad propagation
- checker result unknown or failed
- non-boolean checker result contract
- real signing, real headers, or HTTP POST capability
- unsafe render / serialization settings

## Internal Wiring

Step 6G-IW now requires `credential_presence_checker_contract_ready=true` after
`credential_presence_adapter_ready=true`.

The internal wiring keeps only sanitized contract flags. It does not store or
render credential values, credential metadata, sentinel text, checker result
details, raw request, raw response, or real IDs.

## Non-Goals

This Step does not implement:

- real credential presence check implementation
- env access
- real checker attachment or execution
- actual environment presence check
- real credential injection
- real credential handle creation
- real signing value generation
- real header value generation
- real HTTP transport
- real order endpoint call
- live order execution

Future real credential presence check implementation, future real credential
injection, future real signing, and future real transport must be separate
Steps. Future real execution requires a new final confirmation and fresh
preflight.

Retry, loop, add order, change order, cancel order, and close order remain
forbidden. Raw/secret/ID exposure remains forbidden.
