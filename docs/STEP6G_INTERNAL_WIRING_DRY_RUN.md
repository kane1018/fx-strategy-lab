# Step 6G Internal Wiring Dry Run

Step 6G-IW adds a fake/sanitized internal wiring model for the existing Step 6G
safe pieces. It connects PB, EB, AD, RA, TC, and ST in one dry-run chain without
API calls, HTTP POST, an order endpoint, `live_order_once`, or a real order.

## Background

- Step 6G-IR concluded CASE 2.
- PB / EB / AD / RA / TC / ST were individually safe, but there was no single
  fake/sanitized wiring check proving they were compatible in one snapshot.
- Real signing and real transport remain out of scope until this dry-run
  boundary is green.

## Implemented Model

- New internal wiring model:
  `backend/app/live_verification/live_order_real_step6g_internal_wiring.py`
- New tests:
  `backend/app/tests/test_live_verification_live_order_real_step6g_internal_wiring.py`

The model builds a fake/sanitized chain through:

- PB: post route bridge
- EB: fake runtime bridge
- AD: controlled adapter with fake transport
- RA: real adapter contract with stub transport
- TC: low-level transport core
- ST: signing contract and private order transport contract

## Safety Boundary

The dry-run input uses only sentinel metadata:

- `USD_JPY` / `BUY` / `100` / `MARKET`
- fake final confirmation exact-match flags
- fake final-confirmation and POST-immediate preflight pass flags
- dummy approval fingerprint / sha256 prefix
- contract-only signing and transport flags

It does not reuse an old final confirmation, generate or show an approval command,
execute fresh preflight, use credentials, generate signatures, create header
values, store serialized body text, or expose raw request/response or real IDs.

## Ready State

Ready means:

- `STEP6G_INTERNAL_WIRING_READY_NO_API_NO_POST`
- PB / EB / AD / RA / TC / ST all ready
- `http_post_executed=false`
- `order_endpoint_called=false`
- `live_order_once_called=false`
- `credential_values_provided=false`
- `signature_value_generated=false`
- `header_values_present=false`
- `post_allowed_this_step=false`
- `post_executed=false`
- retry / loop / add / change / cancel / close disabled

Ready is not live execution permission. Fake final confirmation and fake
preflight are not real approval or real preflight evidence.

## Blockers

The model blocks:

- order intent mismatch or Codex-inferred intent
- final confirmation reuse or missing exact-match evidence
- approval artifact / validation / exact-match failures
- approval command full text, copy/display/save, raw, secret, or real ID exposure
- final-confirmation or POST-immediate preflight failures
- nonzero open positions or active orders
- stale ticker or spread too wide
- attempt count or retry/loop/mutation flags
- PB / EB / AD / RA / TC / ST status or schema mismatch
- credential values, signature values, or header values
- HTTP POST, order endpoint, or `live_order_once` execution flags
- Step 4 approval phrase spoofing or ledger mutation

## Future Work

Future real execution still requires a separate Step with a new final
confirmation, fresh final-confirmation preflight, fresh POST-immediate preflight,
one POST maximum, no retry, and sanitized reconciliation. A future dummy signing
or transport-interface Step may follow this dry-run, but real signing and real
transport remain separate reviewed Steps.
