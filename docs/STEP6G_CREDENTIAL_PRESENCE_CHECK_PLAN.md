# Step 6G Credential Presence Check Skeleton

## Scope

Step 6G-PC follows the Step 6G-PC-R planning review. It adds a credential
presence check skeleton that converts operator-provided boolean/sentinel
metadata into a safe contract flag.

This is not a real environment presence check. It does not read env or `.env`.
It does not use credential values, credential metadata, or real credential
handles. It does not generate real signatures or real header values. It does
not execute API calls, HTTP POST, order endpoint calls, or `live_order_once`.

## Contract

The ready mode is `OPERATOR_PROVIDED_SENTINEL_ONLY`.

The ready status is
`CREDENTIAL_PRESENCE_CHECK_READY_OPERATOR_PROVIDED_NO_ENV`.

Ready requires:

- credential boundary ready
- credential handle ready
- credential injection ready
- operator assertion provided
- operator assertion is boolean-only
- operator sentinel received
- operator sentinel is fresh
- operator sentinel is not reused
- operator sentinel is not stale
- operator sentinel is not from a previous turn
- sentinel value/hash/fingerprint/length are not present, displayed, or saved
- credential values and credential metadata are not present
- no real environment presence check
- no env, `.env`, or printenv access
- no broad propagation or saving of the presence result
- no real signing, real headers, or HTTP POST capability

## Safety Defaults

Ready still means:

- `sentinel_value_present=false`
- `credential_values_present=false`
- `credential_metadata_present=false`
- `credential_presence_checked_against_environment=false`
- `env_access_requested=false`
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

- wrong presence mode
- missing credential boundary / handle / injection prerequisites
- missing or non-boolean operator assertion
- missing operator sentinel
- stale, reused, or previous-turn sentinel
- sentinel value/hash/fingerprint/length exposure
- credential value or metadata presence
- real environment presence check
- env / `.env` / printenv access
- broad propagation or saving of the presence result
- real signing, real headers, or HTTP POST capability
- unsafe render / serialization settings

## Internal Wiring

Step 6G-IW now requires `credential_presence_check_ready=true` in addition to
credential boundary, credential handle, and credential injection readiness.

The internal wiring keeps only sanitized contract flags. It does not store or
render the operator sentinel text. It does not render or serialize credential
values, credential metadata, raw request, raw response, or real IDs.

## Non-Goals

This Step does not implement:

- real credential presence check
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
