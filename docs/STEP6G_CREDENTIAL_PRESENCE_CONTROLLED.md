# Step 6G Credential Presence Controlled Check

## Summary

Step 6G-PC-OX-R-CRED-P-C adds a controlled credential presence check for the
first narrow env-access boundary after ENV-GATE.

This Step allows only process env access needed to convert required credential
presence into safe booleans. It does not read `.env` or `.env.example` files,
does not expose env actual names, and does not expose credential values,
lengths, hashes, fingerprints, or metadata.

## Scope

Allowed in this Step:

- process env presence check for required credential safe labels;
- safe per-label presence booleans;
- safe all-required-present boolean;
- safe status labels and blocked reason labels;
- renderer/asdict summaries that contain only safe labels and booleans.

Not allowed in this Step:

- `.env` file read;
- `.env.example` file read;
- credential value display, return, storage, or logging;
- credential length, hash, fingerprint, preview, prefix, or suffix;
- credential metadata actual value;
- env actual name display, return, storage, or logging;
- credential injection;
- real signing or real headers generation;
- real transport;
- API call, read-only API call, public API call, Private API call;
- HTTP POST, order endpoint, or `live_order_once`;
- actual result receipt or actual receipt handoff;
- fresh preflight, final confirmation, or live-money Step 6G retry.

## Controlled Contract

The implementation is in
`backend/app/live_verification/live_order_real_credential_presence_controlled.py`.

It defines:

- `CREDENTIAL_PRESENCE_CONTROLLED_IMPLEMENTATION_ONLY`;
- `CREDENTIAL_PRESENCE_PRESENT_NO_POST`;
- `CREDENTIAL_PRESENCE_MISSING_NO_POST`;
- safe blocked statuses for unknown, failed, unavailable, timeout, unsafe
  exposure, actual execution/receipt, API/POST, signing/transport, and
  unsupported input;
- required credential safe labels that are not env actual names;
- result fields limited to safe booleans, safe labels, status, blocked reasons,
  and a recommended next step.

The result does not contain raw env values, env actual names, credential values,
credential lengths, credential hashes, credential fingerprints, credential
metadata, signature values, header values, raw requests, raw responses, or real
IDs.

## Semantics

- Credential present is not POST permission.
- Credential present is not signing permission.
- Credential present is not API permission.
- Credential present is not `live_order_once` permission.
- Credential present is not fresh preflight.
- Credential present is not final confirmation.
- Credential present is not actual checker execution beyond the presence-only
  check.
- Credential present is not actual result receipt or actual receipt handoff.
- `READY_CONFIRMED` is not POST permission.
- `NOT_PROVIDED` is not actual result receipt.
- Receipt/policy/lifecycle/non-execution ready is not actual handoff
  permission.

## Fail-Closed Rules

The controlled presence check blocks on:

- missing required presence;
- unknown, failed, unavailable, or timeout presence state;
- `.env` or `.env.example` file read;
- env actual name exposure;
- credential value, length, hash, fingerprint, or metadata exposure;
- actual checker execution beyond presence;
- actual result receipt or actual receipt handoff;
- API/POST/order endpoint/`live_order_once` attempt;
- real signing, real headers, or real transport attempt;
- fresh preflight or final confirmation.

Missing, unknown, failed, unavailable, and timeout states are not retried inside
this Step.

## Internal Wiring

Step 6G-IW now includes `credential_presence_controlled_ready` as a minimal gate.
The IW path still does not read real env. It uses a fake presence source for the
dry-run contract and keeps the actual process env read isolated to the controlled
presence module.

IW remains fail-closed for:

- controlled presence not checked;
- missing required credentials;
- unknown/failed/unavailable/timeout presence;
- unsafe exposure;
- API/POST/live_order_once;
- signing/transport;
- actual checker execution beyond presence;
- actual result receipt or actual receipt handoff.

## Next Step

Recommended next Step:

```text
Step 6G-PC-OX-R-CRED-P-V:
credential presence controlled implementation boundary review / no credential value exposure / no API / no POST / no code change
```

If the controlled presence implementation and self-review remain clean, a later
decision gate may consider credential injection. That later gate must still avoid
credential value display, credential length/hash/fingerprint display, API calls,
POST, order endpoints, `live_order_once`, real signing, real transport, fresh
preflight, final confirmation, and live-money Step 6G retry.
