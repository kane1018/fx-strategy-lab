# Step 6G-TF Ticker Age Sanitizer Fix

## Summary

Step 6G-F stopped fail-closed after the final confirmation phrase was received.
The approval artifact regeneration and fingerprint match passed, but the
POST-before fresh preflight sanitizer tried to read `Ticker.timestamp` from the
GMO Public ticker object. The normalized ticker shape returned by
`GmoPublicMarketDataClient.fetch_ticker()` uses `Ticker.time`, not
`Ticker.timestamp`.

No HTTP POST was executed. No order endpoint was called. `live_order_once` was
not called. No real order was attempted.

## Scope

This Step 6G-TF change is code/test/docs only. It does not run Step 6G, does not
reuse the previous final confirmation phrase, and does not call any API.

## Static Shape Confirmation

`backend/app/shadow/gmo_public.py` normalizes the public `/v1/ticker` response
into `app.shadow.models.Ticker`:

- `symbol`
- `bid`
- `ask`
- `time`

The sanitizer therefore treats `time` as the primary timestamp field. It also
accepts `timestamp` as an explicit fallback for compatible sanitized fake inputs,
but missing or unsupported time fields fail closed.

## Fix

The Step 6E/Step 6G preflight sanitizer now converts ticker objects into
sanitized ticker fields without exposing raw ticker data:

- `ticker_symbol`
- `ticker_bid`
- `ticker_ask`
- `ticker_spread_jpy`
- `ticker_age_seconds`
- `ticker_check_passed`
- `ticker_time_field`
- sanitized blocked reasons

The helper stores no raw request, raw response, headers, signature, credentials,
or real IDs.

## Fail-Closed Policy

- Missing time field: `ticker_check_passed=false`
- Unsupported time value: `ticker_check_passed=false`
- Stale ticker age greater than 30 seconds: `ticker_check_passed=false`
- Future timestamp down to `-5` seconds: allowed as minor clock skew
- Future timestamp less than `-5` seconds: `ticker_check_passed=false`
- Spread greater than `0.01` JPY: `ticker_check_passed=false`

## Step 6G Re-run Policy

The previous Step 6G-F final confirmation phrase is expired. Any future Step 6G
attempt must start from the beginning, regenerate the approval artifact in that
task, run fresh preflight checks, show a new final confirmation gate, and receive
a new exact final confirmation phrase before any one-shot POST can be considered.

## Boundaries

This fix does not:

- call real API;
- call read-only API;
- call public API;
- call Private API;
- call broker code;
- run fresh preflight;
- execute HTTP POST;
- call any order endpoint;
- call `live_order_once`;
- generate or send an order payload;
- display or save raw request/response, headers, signature, credentials, or real IDs.

## Tests

Tests cover:

- actual GMO Public normalized `Ticker(time=...)` shape;
- objects without `.timestamp`;
- timestamp fallback fake input;
- missing timestamp fail-closed;
- stale ticker fail-closed;
- future clock skew within and beyond the allowed range;
- spread pass/fail;
- serialization safety.
