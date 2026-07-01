# Step 6G Transport Controlled Boundary

## Summary

Step 6G-PC-OX-R-TRANSPORT-C adds a controlled transport boundary after the
controlled signing and headers boundary.

This Step does not execute real transport, does not call APIs, and does not
execute HTTP POST. It converts a safe controlled signing/headers result into
fixed safe transport labels, safe statuses, and booleans only.

## Scope

Allowed in this Step:

- safe controlled signing/headers prerequisite booleans;
- fixed safe transport label;
- safe transport status;
- controlled transport ready boolean;
- one POST max, no retry, fresh preflight, final confirmation, and sanitized
  result required booleans;
- safe blocked reason labels;
- renderer/asdict summaries that contain only safe labels, safe statuses, and
  booleans.

Not allowed in this Step:

- real transport execution;
- HTTP client execution;
- API call, read-only API call, public API call, or Private API call;
- HTTP POST, order endpoint call, or `live_order_once`;
- raw request generation, display, return, storage, or logging;
- raw response receipt, display, return, storage, or logging;
- request body or response body display, return, storage, or logging;
- endpoint actual value or order endpoint actual value display;
- credential value display, return, storage, or logging;
- signature value display, return, storage, or logging;
- headers value display, return, storage, or logging;
- real ID, account ID, or order ID display, return, storage, or logging;
- broker response or API response display, return, storage, or logging;
- `.env` or `.env.example` file read;
- real signing or real headers generation;
- actual checker execution, actual result receipt, or actual receipt handoff;
- fresh preflight, final confirmation, or live-money Step 6G retry.

## Controlled Contract

The implementation is in
`backend/app/live_verification/live_order_real_transport_controlled.py`.

It defines:

- `TRANSPORT_CONTROLLED_IMPLEMENTATION_ONLY`;
- `CONTROLLED_TRANSPORT_BOUNDARY` as the fixed safe transport label;
- `TRANSPORT_READY_NO_API_NO_POST`;
- blocked statuses for missing signing/headers, unknown, failed, unavailable,
  timeout, unsafe exposure, credential value exposure, signature value exposure,
  headers value exposure, raw request exposure, raw response exposure, API
  attempt, POST attempt, order endpoint, `live_order_once`, and
  preflight/confirmation boundary violations;
- result fields limited to safe booleans, fixed safe labels, statuses, blocked
  reasons, future blocker booleans, and a recommended next step.

The result does not contain credential values, signature values, headers values,
raw requests, raw responses, request bodies, response bodies, endpoint actual
values, order endpoint actual values, real IDs, account IDs, order IDs, broker
responses, or API responses.

## Semantics

- Controlled signing/headers ready is a prerequisite, not automatic transport
  execution permission.
- Transport controlled ready is not API permission.
- Transport controlled ready is not POST permission.
- Transport controlled ready is not order endpoint permission.
- Transport controlled ready is not `live_order_once` permission.
- Transport controlled ready is not actual checker execution.
- Transport controlled ready is not actual result receipt.
- Transport controlled ready is not actual receipt handoff.
- Transport controlled ready is not fresh preflight.
- Transport controlled ready is not final confirmation.
- Transport controlled ready is not live-money Step 6G retry.

## Fail-Closed Rules

The controlled transport boundary blocks on:

- missing controlled signing/headers prerequisite;
- unknown, failed, unavailable, or timeout state;
- unsafe exposure attempt;
- credential value, signature value, headers value, raw request, raw response,
  request body, response body, endpoint actual value, ID, broker response, or API
  response exposure attempt;
- API attempt, HTTP client presence, or real transport attempt;
- POST, order endpoint, or `live_order_once` attempt;
- actual checker execution, actual result receipt, or actual receipt handoff;
- fresh preflight or final confirmation attempt;
- missing future POST blockers.

Missing, unknown, failed, unavailable, timeout, and unsafe states are not retried
inside this Step.

## Future POST Blockers

This Step does not implement POST execution. Before any future POST-capable Step,
separate gates must still fix:

- one POST max enforcement;
- no retry enforcement;
- timeout fail-closed behavior;
- automatic retry prohibition for unknown, failed, unavailable, or timeout
  states;
- fresh preflight immediately before POST;
- new final confirmation before POST;
- sanitized POST result handling.

## Internal Wiring

Step 6G-IW includes `transport_controlled_ready` as a minimal gate after
`signing_headers_controlled_ready`.

IW remains fail-closed for:

- controlled transport not ready;
- controlled signing/headers missing or not ready;
- unknown/failed/unavailable/timeout state;
- unsafe exposure;
- credential value, signature value, headers value, raw request, raw response,
  request body, response body, endpoint actual value, ID, broker response, or API
  response exposure attempt;
- real transport or API attempt;
- POST, order endpoint, or `live_order_once` attempt;
- actual checker execution, actual result receipt, or actual receipt handoff;
- fresh preflight or final confirmation.

Even when `transport_controlled_ready=true`, these remain false:

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
Step 6G-PC-OX-R-TRANSPORT-V:
transport controlled implementation boundary review / no API call / no POST / no code change
```

That review must still avoid API calls, POST, order endpoints,
`live_order_once`, raw request display, raw response display, credential value
display, signature value display, headers value display, real ID display, fresh
preflight, final confirmation, actual result receipt, actual receipt handoff,
and live-money Step 6G retry.
