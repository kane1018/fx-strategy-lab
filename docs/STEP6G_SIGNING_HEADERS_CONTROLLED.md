# Step 6G Signing Headers Controlled Boundary

## Summary

Step 6G-PC-OX-R-SIGN-C adds a controlled signing and headers boundary after
controlled credential injection.

This Step does not execute real signing and does not generate real API headers.
It converts a safe controlled credential injection result into fixed safe
signing/header labels, safe statuses, and booleans only.

## Scope

Allowed in this Step:

- safe controlled credential injection prerequisite booleans;
- fixed safe signing and headers labels;
- safe signing and headers statuses;
- controlled signing and headers ready booleans;
- safe blocked reason labels;
- renderer/asdict summaries that contain only safe labels, safe statuses, and
  booleans.

Not allowed in this Step:

- credential value display, return, storage, or logging;
- raw handle display, return, storage, or logging;
- credential length, hash, fingerprint, preview, prefix, or suffix;
- credential metadata actual value;
- env actual name display, return, storage, or logging;
- `.env` or `.env.example` file read;
- real signing execution;
- real headers generation;
- signature value display, return, storage, or logging;
- headers value display, return, storage, or logging;
- signature length, hash, or fingerprint;
- headers metadata actual value;
- real transport;
- API call, read-only API call, public API call, Private API call;
- HTTP POST, order endpoint, or `live_order_once`;
- actual checker execution, actual result receipt, or actual receipt handoff;
- fresh preflight, final confirmation, or live-money Step 6G retry.

## Controlled Contract

The implementation is in
`backend/app/live_verification/live_order_real_signing_headers_controlled.py`.

It defines:

- `SIGNING_HEADERS_CONTROLLED_IMPLEMENTATION_ONLY`;
- `CONTROLLED_SIGNING_BOUNDARY` as the fixed safe signing label;
- `CONTROLLED_HEADERS_BOUNDARY` as the fixed safe headers label;
- `SIGNING_HEADERS_READY_NO_TRANSPORT`;
- blocked statuses for missing injection, unknown, failed, unavailable,
  timeout, unsafe exposure, credential value exposure, raw handle exposure,
  signature value exposure, headers value exposure, metadata exposure,
  transport/API, POST/order, and `live_order_once`;
- result fields limited to safe booleans, fixed safe labels, statuses, blocked
  reasons, and a recommended next step.

The result does not contain credential values, raw handle values, credential
lengths, hashes, fingerprints, credential metadata actual values, env actual
names, signature values, headers values, signature lengths, hashes,
fingerprints, headers metadata actual values, raw requests, raw responses, or
real IDs.

## Semantics

- Controlled credential injection ready is a prerequisite, not automatic signing
  permission.
- Signing controlled ready is not API permission.
- Signing controlled ready is not POST permission.
- Signing controlled ready is not real transport permission.
- Signing controlled ready is not order endpoint permission.
- Signing controlled ready is not `live_order_once` permission.
- Signing controlled ready is not actual checker execution.
- Signing controlled ready is not actual result receipt.
- Signing controlled ready is not actual receipt handoff.
- Signing controlled ready is not fresh preflight.
- Signing controlled ready is not final confirmation.
- Signing controlled ready is not live-money Step 6G retry.
- Headers controlled ready is not headers value display permission.
- Headers controlled ready is not API, POST, real transport, order endpoint, or
  `live_order_once` permission.

## Fail-Closed Rules

The controlled signing and headers boundary blocks on:

- missing controlled credential injection prerequisite;
- unknown, failed, unavailable, or timeout state;
- unsafe exposure attempt;
- credential value, raw handle, metadata, length, hash, fingerprint, or env
  actual name exposure attempt;
- signature value, length, hash, or fingerprint exposure attempt;
- headers value or metadata exposure attempt;
- real signing or real headers generation attempt;
- real transport or API attempt;
- POST, order endpoint, or `live_order_once` attempt;
- actual checker execution, actual result receipt, or actual receipt handoff;
- fresh preflight or final confirmation.

Missing, unknown, failed, unavailable, and timeout states are not retried inside
this Step.

## Internal Wiring

Step 6G-IW includes `signing_headers_controlled_ready` as a minimal gate after
`credential_injection_controlled_ready`.

IW remains fail-closed for:

- controlled signing/headers not ready;
- controlled credential injection missing or not ready;
- unknown/failed/unavailable/timeout state;
- unsafe exposure;
- credential value, raw handle, metadata, length, hash, fingerprint, or env
  actual name exposure attempt;
- signature value, length, hash, or fingerprint exposure attempt;
- headers value or metadata exposure attempt;
- real signing, real headers generation, real transport, or API attempt;
- POST, order endpoint, or `live_order_once` attempt;
- actual checker execution, actual result receipt, or actual receipt handoff;
- fresh preflight or final confirmation.

Even when `signing_headers_controlled_ready=true`, these remain false:

- `real_transport_allowed`;
- `api_call_allowed`;
- `post_allowed_this_step`;
- `post_executed`;
- `http_post_executed`;
- `order_endpoint_called`;
- `live_order_once_called`;
- `fresh_preflight_executed`;
- `final_confirmation_received`.

## Next Step

Recommended next Step:

```text
Step 6G-PC-OX-R-SIGN-V:
signing and headers controlled implementation boundary review / no signature value exposure / no API / no POST / no code change
```

That review must still avoid credential value display, raw handle display,
credential length/hash/fingerprint display, metadata actual value display,
signature value display, headers value display, signature length/hash/fingerprint
display, headers metadata actual value display, real transport, API calls, POST,
order endpoints, `live_order_once`, actual result receipt, actual receipt
handoff, fresh preflight, final confirmation, and live-money Step 6G retry.
