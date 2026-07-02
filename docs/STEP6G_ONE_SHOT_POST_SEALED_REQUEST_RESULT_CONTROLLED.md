# Step 6G One-Shot POST Sealed Request Result Controlled

Step 6G-PC-OX-R-SEALED-REQUEST-BODY-RESULT-MAPPER-C implements the
safe-only sealed request/body/result mapper foundation for the future
POST-only source path.

This step is not actual HTTP POST, not an order endpoint call, not
`live_order_once` execution, not a POST-specific confirmation step, and not a
credential/signing/header provider step.

## Scope

Implemented in:

- `backend/app/live_verification/live_order_real_one_shot_post_sealed_request_result_controlled.py`

The foundation exposes:

1. sealed request model safe summary
2. sealed body builder safe summary from the existing controlled preview
3. sealed endpoint label
4. source-owned client order id strategy skeleton
5. safe transport-result to sanitized-result mapper

The module does not import or call:

- `live_order_once`
- broker clients
- Private API clients
- HTTP clients
- env readers
- credential readers
- signing providers
- header builders
- ledger writers
- receipt handoff code

## Safe Summary

The sealed request/body summary exposes only safe labels, booleans, counts, and
categories:

- `sealed_request_model_ready`
- `sealed_body_builder_ready`
- `sealed_endpoint_label_ready`
- `safe_result_mapper_ready`
- `sealed_request_label`
- `sealed_body_label`
- `sealed_endpoint_label`
- `source_owned_client_order_id_strategy_required`
- `source_owned_client_order_id_strategy_ready`
- `client_order_id_strategy_non_ledger`
- `client_order_id_actual_value_generated=false`
- `client_order_id_actual_value_exposed=false`
- `approved_primitive_actual_source_available=false`

It never exposes raw body values, endpoint actual values, credential values,
signature values, headers values, raw responses, broker/API responses, or real
IDs.

## Body Builder Boundary

The sealed body builder accepts only the existing controlled executable order
preview safe fields:

- symbol
- side
- order type
- size
- time-in-force label
- environment label
- risk label
- safe order source label

It fails closed when the safe candidate is missing, ambiguous, inferred by
Codex, unsupported, or when any raw/ID/value exposure attempt is indicated.

The builder does not serialize or return the actual outbound body. It only
confirms that the later source factory has enough safe candidate information to
proceed to the credential/signing-provider design step.

## Client Order Id Strategy Skeleton

This step adds only the safe skeleton:

- source-owned strategy required
- source-owned strategy ready
- non-ledger strategy flag
- safe strategy label

It does not generate, store, display, return, or validate an actual client order
id value.

## Safe Result Mapper

The mapper accepts safe transport categories only:

- accepted
- rejected
- failed
- timeout
- unknown
- unavailable

It maps them to sanitized result categories without raw responses, broker/API
payloads, IDs, retry, ledger updates, or receipt handoff.

Timeout, unknown, unavailable, failed, raw exposure, ID exposure, retry, ledger,
and receipt-handoff attempts fail closed.

## What This Step Did Not Do

This implementation step did not:

- execute actual HTTP POST
- call an order endpoint
- call `live_order_once`
- obtain POST-specific confirmation
- read `.env` or env files
- handle credential values
- generate signatures
- generate headers
- serialize or expose a raw request body
- expose endpoint actual values
- expose raw responses or broker/API responses
- expose account/order/transaction/client order id values
- update ledger state
- persist an attempt counter
- receive or hand off actual receipts
- retry or repost
- make the current/default approved primitive actual source available

## Next Step

Recommended next step:

```text
Step 6G-PC-OX-R-SEALED-CREDENTIAL-SIGNING-PROVIDER-C
```

That next step may design the credential/signing/header provider, but it must
still avoid actual HTTP POST, POST-specific confirmation, credential value
display, signature value display, headers value display, raw request/response
exposure, ledger updates, receipt handoff, retry, and repost.
