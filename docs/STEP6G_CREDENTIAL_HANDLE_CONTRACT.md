# Step 6G Credential Handle Contract

Step 6G-CH adds a credential handle contract after the Step 6G credential
boundary skeleton. It is contract-only. It does not create a real credential
handle, use credential values, check real credential presence against the real
environment, read env, read `.env`, generate real signatures, generate real
header values, execute API calls, execute HTTP POST, call an order endpoint,
call `live_order_once`, or place a real order.

## Background

- Step 6G-CB added a boundary-only credential contract with no credential value,
  no real environment presence check, no env access, and no POST capability.
- Step 6G-IW already requires credential boundary readiness before the
  fake/sanitized internal wiring can be ready.
- The next safe boundary is a handle contract that defines how future real
  credential injection must remain separated from credential values and handle
  internals.

## Implemented Contract

- New contract module:
  `backend/app/live_verification/live_order_real_credential_handle.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_credential_handle.py`
- Minimal internal wiring integration:
  `backend/app/live_verification/live_order_real_step6g_internal_wiring.py`

The handle contract accepts metadata only:

- `handle_mode=HANDLE_CONTRACT_ONLY`
- `credential_boundary_ready=true`
- `handle_requested=true`
- `handle_created=false`
- false flags for handle value, secret, token, key material, identifier, display,
  save, metadata display, and metadata save
- false flags for handle length, hash, fingerprint, preview, prefix, and suffix
  availability
- false flags for env access, `.env` access, credential values provided, and
  credential values loaded
- false flags for real signature generation, real header generation, and HTTP
  POST capability
- `safe_to_render=true` and `safe_to_serialize=true`

## Ready State

Ready means:

- `CREDENTIAL_HANDLE_READY_NO_VALUE_NO_ENV`
- `credential_handle_ready=true`
- `handle_mode=HANDLE_CONTRACT_ONLY`
- `credential_boundary_ready=true`
- `handle_requested=true`
- `handle_created=false`
- `handle_contains_value=false`
- `handle_contains_identifier=false`
- `handle_metadata_exposed=false`
- `credential_values_provided=false`
- `credential_values_loaded=false`
- `env_access_requested=false`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

Ready is not real credential injection permission, not real signing permission,
not real transport permission, and not POST permission.

## Blockers

The model blocks:

- non-`HANDLE_CONTRACT_ONLY` mode
- missing credential boundary readiness
- missing handle request contract flag
- real handle creation
- handle value, secret, token, or key material presence
- handle identifier or handle metadata availability such as length, hash,
  fingerprint, preview, prefix, or suffix
- handle value or metadata display/save
- unsafe render/serialize flags
- env / `.env` access request
- credential values provided or loaded
- real signature generation, real header generation, HTTP POST capability, POST
  execution, order endpoint call, or `live_order_once` call
- retry or loop flags

## Internal Wiring

Step 6G-IW now requires the credential handle contract to be ready. Handle
creation, handle value presence, handle identifier presence, or handle metadata
exposure keep internal wiring blocked as raw/secret exposure. A missing handle
contract ready flag keeps internal wiring blocked in the signing-contract group.

## Safety Boundary

This Step does not create a real credential handle, use real credentials, confirm
real credential presence, read env, read `.env`, use `os.environ` or `getenv`,
display or save credential values, expose handle id/token/secret/key material,
display credential length/hash/fingerprint/preview/prefix/suffix, generate real
signatures, generate real header values, display or save raw request/response
data, expose real IDs, mutate ledger state, or spoof Step 4 approval.

Future real credential injection, future real signing, and future real transport
must each be separate reviewed Steps. Future real execution still requires a new
final confirmation, fresh final-confirmation preflight, fresh POST-immediate
preflight, one POST maximum, no retry, and sanitized post-attempt
reconciliation.
