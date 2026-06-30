# Step 6G Credential Injection Skeleton

## Summary

Step 6G-CI adds a credential injection skeleton after Step 6G-CH credential
handle contract. This is a pure contract/skeleton layer for future real
credential injection, not an implementation of real credential injection.

The skeleton is `INJECTION_SKELETON_ONLY`. It requires credential boundary ready
and credential handle ready, but it does not create a handle and does not inject
real credentials.

## Implemented Scope

- Added `backend/app/live_verification/live_order_real_credential_injection.py`.
- Added `backend/app/tests/test_live_verification_live_order_real_credential_injection.py`.
- Connected the credential injection ready gate to Step 6G-IW internal wiring.
- Added no-order import/dependency guard coverage for the new module.

## Safety Contract

The credential injection skeleton:

- does not use credential values;
- does not perform real credential injection;
- does not create a real credential handle;
- does not use env, `.env`, `os.environ`, `getenv`, or dotenv;
- does not check credential presence against the real environment;
- does not use or expose handle id, token, secret, key material, length, hash,
  fingerprint, preview, prefix, or suffix;
- does not generate real signatures;
- does not generate real header values;
- does not execute API calls;
- does not execute HTTP POST;
- does not call an order endpoint;
- does not call `live_order_once`.

Ready state preserves:

- `credential_injection_ready=true`
- `injection_requested=true`
- `injection_performed=false`
- `real_credential_values_available=false`
- `real_credential_values_injected=false`
- `credential_values_provided=false`
- `credential_values_loaded=false`
- `credential_metadata_available=false`
- `handle_created=false`
- `handle_contains_value=false`
- `handle_contains_identifier=false`
- `env_access_requested=false`
- `can_generate_real_signature=false`
- `can_generate_real_headers=false`
- `can_execute_http_post=false`
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

## Block Conditions

The skeleton blocks when:

- injection mode is not `INJECTION_SKELETON_ONLY`;
- credential boundary is not ready;
- credential handle is not ready;
- injection is not requested as a skeleton contract;
- injection has already been performed;
- real credential values are available or injected;
- credential values are provided or loaded;
- credential metadata is available, displayed, or saved;
- a handle is created or contains a value/identifier;
- handle values are displayed or saved;
- env / `.env` access is requested;
- credential presence is checked against the environment;
- real signature/header generation or HTTP POST capability is requested;
- rendering or serialization is unsafe;
- retry or loop behavior is enabled.

## Internal Wiring

Step 6G-IW now requires the credential injection skeleton to be ready. The IW
ready path remains fake/sanitized only and still preserves:

- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `post_allowed_this_step=false`
- `post_executed=false`

If injection has been performed, real credential values are injected, or
credential metadata is available, IW blocks as raw/secret exposure.

## Future Work

Future real credential injection must be a separate Step. Future real signing
and real transport must also be separate Steps. Future real execution requires a
new final confirmation and fresh preflight.

Retry, loop, add, change, cancel, and close order paths remain prohibited.
