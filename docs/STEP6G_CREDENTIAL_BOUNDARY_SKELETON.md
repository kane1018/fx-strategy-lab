# Step 6G Credential Boundary Skeleton

Step 6G-CB adds a credential boundary skeleton after the Step 6G HTTP transport
interface skeleton. It is boundary-only. It does not use real credentials,
check credential presence against the real environment, read env, read `.env`,
generate real signatures, generate real header values, execute API calls,
execute HTTP POST, call an order endpoint, call `live_order_once`, or place a
real order.

## Background

- Step 6G-HT added an interface-only HTTP transport boundary with no HTTP
  client, no API, and no POST.
- Step 6G-IW now requires HTTP transport interface readiness before the
  fake/sanitized internal wiring can be ready.
- The next safe boundary is a credential contract that defines what must still
  be blocked before any future real signing work.

## Implemented Boundary

- New boundary skeleton:
  `backend/app/live_verification/live_order_real_credential_boundary.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_credential_boundary.py`
- Minimal internal wiring integration:
  `backend/app/live_verification/live_order_real_step6g_internal_wiring.py`

The boundary accepts metadata only:

- `boundary_mode=BOUNDARY_ONLY`
- false flags for real credential request, credential values provided, credential
  values loaded, real environment presence check, env access, `.env` access, and
  `printenv`
- false flags for credential length, hash, fingerprint, preview, prefix, and
  suffix availability
- false flags for credential value display/save
- prerequisite readiness for signing contract, dummy signing, and HTTP transport
  interface
- false flags for real signature generation, real header generation, and HTTP
  POST capability

## Ready State

Ready means:

- `CREDENTIAL_BOUNDARY_READY_NO_CREDENTIAL_NO_ENV`
- `credential_boundary_ready=true`
- `boundary_mode=BOUNDARY_ONLY`
- `real_credentials_requested=false`
- `credential_values_provided=false`
- `credential_values_loaded=false`
- `credential_presence_checked_against_environment=false`
- `env_access_requested=false`
- `credential_metadata_exposed=false`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

Ready is not real credential permission, not real signing permission, and not
POST permission.

## Blockers

The model blocks:

- non-`BOUNDARY_ONLY` mode
- real credential request
- credential value provided
- credential value loaded
- credential presence checked against the real environment
- env / `.env` / `printenv` access request
- credential metadata availability such as length, hash, fingerprint, preview,
  prefix, or suffix
- credential display/save or unsafe render/serialize flags
- real signature generation, real header generation, HTTP POST capability, POST
  execution, order endpoint call, or `live_order_once` call
- retry or loop flags

## Internal Wiring

Step 6G-IW now requires the credential boundary to be ready. Credential values
provided, credential values loaded, env access request, real environment
presence check, or credential metadata exposure keep internal wiring blocked as
raw/secret exposure.

## Safety Boundary

This Step does not use real credentials, confirm real credential presence, read
env, read `.env`, use `os.environ` or `getenv`, display or save credential
values, display credential length/hash/fingerprint/preview/prefix/suffix,
generate real signatures, generate real header values, display or save raw
request/response data, expose real IDs, mutate ledger state, or spoof Step 4
approval.

Future real credential injection, future real signing, and future real transport
must each be separate reviewed Steps. Future real execution still requires a new
final confirmation, fresh final-confirmation preflight, fresh POST-immediate
preflight, one POST maximum, no retry, and sanitized post-attempt
reconciliation.
