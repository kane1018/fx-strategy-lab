# Step 6G Credential Injection Controlled Boundary

## Summary

Step 6G-PC-OX-R-CRED-I-C adds a controlled credential injection boundary after
the controlled credential presence check.

This Step does not inject real credential values for signing. It converts safe
presence booleans into an opaque safe handle label, a safe injection status, and
safe booleans only.

## Scope

Allowed in this Step:

- safe credential presence prerequisite booleans;
- a fixed safe credential handle label;
- safe injection status;
- controlled injection ready boolean;
- safe blocked reason labels;
- renderer/asdict summaries that contain only the safe label, safe status, and
  booleans.

Not allowed in this Step:

- credential value display, return, storage, or logging;
- raw handle display, return, storage, or logging;
- credential length, hash, fingerprint, preview, prefix, or suffix;
- credential metadata actual value;
- env actual name display, return, storage, or logging;
- `.env` or `.env.example` file read;
- real signing or real headers generation;
- real transport;
- API call, read-only API call, public API call, Private API call;
- HTTP POST, order endpoint, or `live_order_once`;
- actual checker execution beyond the controlled boundary;
- actual result receipt or actual receipt handoff;
- fresh preflight, final confirmation, or live-money Step 6G retry.

## Controlled Contract

The implementation is in
`backend/app/live_verification/live_order_real_credential_injection_controlled.py`.

It defines:

- `CREDENTIAL_INJECTION_CONTROLLED_IMPLEMENTATION_ONLY`;
- `CONTROLLED_CREDENTIAL_HANDLE` as the only safe handle label;
- `CREDENTIAL_INJECTION_READY_NO_SIGNING`;
- blocked statuses for missing presence, unknown, failed, unavailable, timeout,
  unsafe exposure, value exposure, raw handle exposure, metadata exposure,
  signing/headers, API/POST, and `live_order_once`;
- result fields limited to safe booleans, the fixed safe label, status, blocked
  reasons, and a recommended next step.

The result does not contain credential values, raw handle values, lengths,
hashes, fingerprints, credential metadata actual values, env actual names,
signature values, header values, raw requests, raw responses, or real IDs.

## Semantics

- Credential injection ready is not signing permission.
- Credential injection ready is not headers generation permission.
- Credential injection ready is not API permission.
- Credential injection ready is not POST permission.
- Credential injection ready is not `live_order_once` permission.
- Credential injection ready is not actual checker execution.
- Credential injection ready is not actual result receipt.
- Credential injection ready is not actual receipt handoff.
- Credential injection ready is not fresh preflight.
- Credential injection ready is not final confirmation.
- Credential injection ready is not live-money Step 6G retry.

## Fail-Closed Rules

The controlled injection boundary blocks on:

- missing controlled presence prerequisite;
- unknown, failed, unavailable, or timeout presence state;
- unsafe exposure attempt;
- credential value exposure attempt;
- raw handle exposure attempt;
- credential metadata exposure attempt;
- credential length, hash, or fingerprint exposure attempt;
- env actual name exposure attempt;
- real signing or real headers generation attempt;
- API/POST/order endpoint/`live_order_once` attempt;
- actual checker execution, actual result receipt, or actual receipt handoff;
- fresh preflight or final confirmation.

Missing, unknown, failed, unavailable, and timeout states are not retried inside
this Step.

## Internal Wiring

Step 6G-IW includes `credential_injection_controlled_ready` as a minimal gate
after `credential_presence_controlled_ready`.

IW remains fail-closed for:

- controlled injection not ready;
- controlled presence missing;
- unknown/failed/unavailable/timeout presence;
- unsafe exposure;
- credential value, raw handle, or metadata exposure attempt;
- signing/headers attempt;
- API/POST/order endpoint/`live_order_once` attempt;
- actual checker execution beyond the controlled boundary;
- actual result receipt or actual receipt handoff.

Even when `credential_injection_controlled_ready=true`, these remain false:

- `real_signing_allowed`;
- `real_headers_generation_allowed`;
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
Step 6G-PC-OX-R-CRED-I-V:
credential injection controlled implementation boundary review / no credential value exposure / no signing / no API / no POST / no code change
```

That review must still avoid credential value display, raw handle display,
length/hash/fingerprint display, metadata actual value display, real signing,
real headers generation, real transport, API calls, POST, order endpoints,
`live_order_once`, actual result receipt, actual receipt handoff, fresh
preflight, final confirmation, and live-money Step 6G retry.
