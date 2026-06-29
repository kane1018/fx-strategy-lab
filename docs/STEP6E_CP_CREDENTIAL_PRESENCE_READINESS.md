# Step 6E-CP Credential Presence Readiness

## Summary

Step 6E-CP documents the credential-presence gate that blocked the Step 6E-R2
market-open retry before any API connection was made. It confirms the expected
credential variable names from source code and defines a presence-only check
policy.

This step is no API and no POST. It never displays, stores, fingerprints,
hashes, or measures credential values.

## Scope

Step 6E-CP is documentation and readiness review only. It may identify expected
credential environment variable names from source code and check whether those
specific names are present in the current process environment as boolean
presence only.

## What this step does

- identifies the private read-only route credential names from source code;
- records the presence-only check policy;
- records the value non-disclosure policy;
- records the `.env` and environment-listing boundaries;
- defines the status meanings for Step 6E-R2 retry readiness;
- hands off the next action when credential presence is missing.

## What this step does not do

Step 6E-CP does not call real API, read-only API, public API, Private API,
broker code, order endpoints, or `live_order_once`. It does not execute HTTP
POST, create or send order payloads, display or save raw request/response,
display or save headers/signatures/credentials, read or change `.env`, list the
environment, read or change ledgers, or show approval command text.

## Why this step exists

Step 6E-R2 reached the private read-only route gate and stopped before API
connection because credential presence was not satisfied in the execution
environment. The route correctly failed closed without printing credential
values.

Step 6E-CP separates that blocker from any API execution attempt so the next
retry can start from an explicit, value-safe precondition.

## Step 6E-R2 blocker

The blocker is credential presence for the private read-only route. Without
both expected variables present, Step 6E-R2 must stop before any API call.

## Expected credential names

The private read-only route in `backend/scripts/check_private_readonly_connection.py`
expects these environment variable names:

- `GMO_FX_API_KEY`
- `GMO_FX_API_SECRET`

These names are allowed to be documented. Values are not.

## Presence check policy

The presence check may inspect only the specific expected names. Output is
limited to:

- `PRESENT`
- `MISSING`

The check must not print values, lengths, prefixes, suffixes, hashes,
fingerprints, or derived identifiers.

## Value non-disclosure policy

Credential values must not be displayed, saved, copied, committed, logged, or
included in Markdown reports. The same rule applies to token values, headers,
signatures, raw request data, raw response data, and real IDs.

## .env policy

Do not display, read, grep, cat, edit, or commit `.env`. If the required
presence is missing, the operator must set the variables manually outside this
task.

## Environment listing policy

Do not run `env`, `printenv`, or any broad environment listing. Only the two
expected variable names may be checked for boolean presence.

## Status meanings

`READY_FOR_STEP6E_R2_RETRY_WITH_CREDENTIAL_PRESENCE` means both expected
variables are present, values were not displayed, `.env` was not read, and no
API was called.

`BLOCKED_STEP6E_CREDENTIAL_PRESENCE_MISSING` means at least one expected
variable is missing. No API should be called.

`BLOCKED_STEP6E_CREDENTIAL_NAMES_UNKNOWN` means the expected names could not be
safely identified from source code. No API should be called.

## If credentials are present

Stop and report readiness. A future Step 6E-R2 retry still requires a separate
explicit request, clean Git state, tests and ruff passing, danger scan, market
window checks, safe route verification, no raw output, no POST, no order
endpoint, and no `live_order_once`.

## If credentials are missing

Stop and report the missing variable names only. The user must manually set the
missing variables in the execution environment. Do not ask for values in chat
and do not inspect `.env`.

## Future Step 6E-R2 handoff

After credential presence is ready, Step 6E-R2 may be requested again as a
separate market-open retry. It remains read-only/preflight only, single-shot,
no POST, no order endpoint, no `live_order_once`, no raw request/response
display or save, no headers/signatures/credentials display, no real IDs, and
`allowed_for_live=false`.

## Tests

Step 6E-CP does not add runtime code. Existing Step 6E-SC, Step 6E-RR, Step 6E,
and no-order guard tests remain the validation surface.

## Handoff summary

Step 6E-CP is complete when the credential names are known, presence is checked
without value exposure, docs record the blocker and policy, and no API/POST
path was called. Step 6F remains blocked until a fresh Step 6E-R2 sanitized
preflight pass exists and the user explicitly requests Step 6F.
