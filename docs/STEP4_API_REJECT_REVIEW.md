# Step 4D Sanitized API Reject Review

## 1. Purpose

Step 4D adds a local-only, sanitized classification path for the previous
one-shot live order API reject.

This task does not:

- execute HTTP POST
- place a live order
- issue an approval id
- choose BUY or SELL
- retry or loop
- add, change, cancel, or close an order
- reset, delete, edit, or overwrite the live order ledger
- display or store raw request, raw response, headers, signature, API key, or
  API secret values

## 1A. Step 4F-B One-Shot Retry Result

Step 4F-B was rerun on 2026-06-26 after the Step 4F approval command alignment.

Sanitized result:

```text
approval_id_prefix: STEP4F-
approval_command_exact_match: true
HTTP_POST_count: 1
symbol: USD_JPY
side: BUY
size: 100
executionType: MARKET
transport_result: success
api_status_success: true
result_unknown: false
retry_count: 0
loop_count: 0
account_assets_after: success
open_positions_count_after: 1
active_orders_count_after: 0
ledger_state: POST_COMPLETED
attempt_count: 1
result_category: success
raw_request_saved: false
raw_response_saved: false
headers_saved: false
signature_saved: false
credential_values_logged: false
```

No raw response, raw request, headers, signature, credential value, order id,
execution id, or request id was displayed or saved. No additional order, retry,
loop, order change, cancellation, close order, or auto-close was performed.

Because `open_positions_count_after=1`, an OPEN position may remain. Any further
action must be handled as a separate task with separate explicit approval.

## 1B. Step 4G-A Read-Only Position Check

Step 4G-A was performed as a read-only position check after Step 4F-B.

Sanitized result:

```text
GMO_FX_API_KEY: set
GMO_FX_API_SECRET: set
ledger_state: POST_COMPLETED
attempt_count: 1
result_category: success
account_assets: success
open_positions_count: 1
active_orders_count: 0
position_count: 1
position_symbol: USD_JPY
position_side: BUY
position_size_total: 100
public_bid: 161.804
public_ask: 161.809
spread_jpy: 0.005
ticker_age_seconds: 0.236
raw_response_saved: false
raw_response_displayed: false
ids_displayed: false
price_detail_displayed: false
```

Classification:

```text
POSITION_CONFIRMED
```

Step 4G-A did not execute HTTP POST, place a new order, add to the position,
close the position, cancel orders, change orders, issue an approval id, issue an
approval gate, or reset the ledger. Position identifiers, order identifiers,
execution identifiers, open price, execution price, detailed P/L, account
details, position details, raw request, raw response, headers, signatures, and
credential values were not displayed or saved.

For a 100-unit USD/JPY position, a 1 JPY move corresponds to an approximate
100 JPY P/L change, and a 0.1 JPY move corresponds to an approximate 10 JPY
P/L change. Any close action must be handled as a separate Step 4G-B task with
separate explicit approval.

## 2. Previous Sanitized State

The previous Step 4B-B outcome was handled only as sanitized facts:

```text
HTTP POST count: 1
transport_result: api_rejected
api_status_success: false
result_unknown: false
retry: 0
loop: 0
open_positions_count_after: 0
active_orders_count_after: 0
ledger_state: POST_COMPLETED
attempt_count: 1
```

The raw response was not displayed and is not required for this review.

Step 4D ledger confirmation was read-only and sanitized:

```text
ledger_exists: true
ledger_state: POST_COMPLETED
attempt_count: 1
post_started_present: true
post_finished_present: true
result_category: api_rejected
```

No ledger mutation was performed.

## 3. Classification Result

Current classification:

```text
REJECT_CAUSE_PARTIAL
```

Reason:

- The sanitized result proves the API rejected the one-shot request.
- No raw response or raw error payload is used.
- No short sanitized error code is available from the previous run.
- Therefore the exact cause must not be guessed.

The likely candidate groups remain:

- API key scope or order permission
- wrong key type or account setting
- IP restriction
- agreement, fee, trial, or API usage procedure incomplete
- account or margin restriction
- signature, timestamp, body, client order id, or symbol-size rule issue
- market, maintenance, or service condition

## 4. Local Classifier

Step 4D adds a local-only classifier that accepts only:

- transport result category
- API success flag as true / false / unknown
- result_unknown flag
- HTTP status class only, such as 4xx or unknown
- optional short sanitized error code
- optional short sanitized message code
- response-data presence as true / false / unknown
- attempt count
- post-check open positions count
- post-check active orders count

It does not accept or store:

- raw response
- raw request
- headers
- signature
- API key
- API secret
- request body
- response body
- endpoint URL
- order id
- root order id
- client order id
- price
- timestamp value
- account detail
- position detail
- order detail

All classifier outputs are non-execution decisions. They cannot authorize a
same-day retry.

## 5. Category Map

Sanitized code prefixes are classified as:

| Prefix group | Category |
| --- | --- |
| `AUTH_`, `PERMISSION_`, `API_PERMISSION_` | `auth_or_permission` |
| `SIGNATURE_`, `SIGN_` | `invalid_signature` |
| `TIMESTAMP_`, `TIME_` | `invalid_timestamp` |
| `BODY_`, `REQUEST_BODY_` | `invalid_request_body` |
| `SIZE_`, `ORDER_SIZE_` | `invalid_order_size` |
| `CLIENT_ORDER_ID_` | `invalid_client_order_id` |
| duplicate or reused client order id prefixes | `duplicate_or_reused_client_order_id` |
| `MARGIN_`, `ACCOUNT_`, `INSUFFICIENT_MARGIN` | `insufficient_margin_or_account_state` |
| `MARKET_`, `SERVICE_`, `MAINTENANCE_` | `market_or_service_unavailable` |
| `RATE_LIMIT_`, `USAGE_` | `rate_limit_or_usage_restriction` |
| missing or unmapped code | `unknown_api_rejected` |

Every category keeps:

```text
is_retry_allowed=false
safe_to_retry_today=false
requires_next_day_or_new_ledger=true
```

## 6. User-Side API Permission Checklist

Before any future Step 4 retry task, the user should confirm in the GMO Coin
management UI or official account settings, outside Codex:

- FX API key is for the Foreign Exchange FX account, not a different product.
- The key has the minimum required order permission for a one-shot new order.
- IP restrictions allow the current execution source if IP allowlisting is
  enabled.
- API usage terms, fee confirmations, and required agreements are complete.
- Trial, campaign, or account-status limitations do not block API ordering.
- The account is not restricted from opening a USD_JPY position.
- Available margin and account state are sufficient for a 100-unit USD_JPY
  MARKET OPEN attempt.
- Market hours, maintenance windows, and important event windows are acceptable.

Do not paste API key or secret values into Codex, ChatGPT, docs, logs, or git.

## 7. Codex-Side Checklist

Codex-side work before any future retry must remain limited to:

- local code review
- tests
- ruff
- git clean check
- sanitized ledger state check
- sanitized read-only preflight in a separate approved task
- short sanitized error code handling if a future run exposes one safely

Codex must not:

- inspect or automate the GMO account management UI
- read `.env`
- print environment variable values
- display API key, secret, signature, or headers values
- display or store raw response
- reset or edit the live order ledger
- issue an approval id during a classification task
- execute HTTP POST during a classification task

## 8. Future Retry Preconditions

A future retry is not allowed by Step 4D itself.

Before any future Step 4 retry:

- use a new task
- use the next trading day or a new explicitly reviewed ledger state
- complete the user-side permission checklist
- complete sanitized read-only preflight
- confirm open positions count is 0 before any new OPEN attempt
- confirm active orders count is 0
- rerun focused tests and ruff
- confirm git clean
- issue a new approval gate only in the Step 4 retry task
- require an exact user approval command
- still use one-shot only, no retry, no loop, no additional order

If a future attempt can safely extract only a short sanitized error code, that
code may be passed to the local classifier. The raw response must still not be
shown, logged, saved, or committed.

## 9. Non-Actions in Step 4D

Step 4D did not perform:

- HTTP POST
- live order
- approval id issuance
- BUY or SELL choice
- read-only Private API connection
- API key presence check
- API secret presence check
- ledger reset
- ledger deletion
- ledger edit
- order retry
- order cancel
- order close
- order change
- additional order
- frontend or public backend API change

## 10. Next Work

Recommended next work:

```text
Step 4E:
User-side API permission/account/IP/settings checklist confirmation.

Step 4F:
Separate sanitized Step 4 retry preflight, only after user-side checks are done.
```

Step 4D itself does not authorize another live order attempt.

## 11. Step 4E User-Reported Order Permission Update

User-side update:

```text
The user reported that the GMO Foreign Exchange FX API key setting now has
"Trade > Order" permission enabled.
```

This is recorded as a user report. Codex did not inspect the GMO management UI
and did not confirm order permission through an API order call.

Interpretation:

- Before this update, missing order permission was one of the strongest
  candidate causes for the previous `api_rejected` result.
- Historical read-only checks for account assets, open positions, and active
  orders had succeeded, so read-only permission was already known to work in a
  previous approved context.
- The effective order permission may not be proven through the API until a
  future explicitly approved POST attempt.
- Step 4E does not perform that POST.

Step 4E local checks:

```text
GMO_FX_API_KEY: missing
GMO_FX_API_SECRET: missing
ledger_exists: true
ledger_state: POST_COMPLETED
attempt_count: 1
result_category: api_rejected
```

Because the current Codex process does not have the required key presence,
Step 4E did not run read-only Private API checks.

Same-day retry decision:

```text
No same-day retry.
```

The one-shot ledger is already `POST_COMPLETED` with `attempt_count=1`, so this
task must not issue an approval id, reset the ledger, or execute another POST.

Before any separate Step 4F retry preflight, the user-side checklist should
confirm:

- order permission remains enabled
- IP restriction allows the execution source, if IP allowlisting is enabled
- account state and available margin permit a 100-unit USD_JPY OPEN attempt
- no required API usage agreement, fee confirmation, or account procedure is
  incomplete
- there is no account restriction, maintenance, or important event window

Step 4F must be a separate task with fresh preflight and a new explicit approval
gate. Step 4E does not authorize a retry.

## 12. Step 4F-A Sanitized Retry Preflight / No POST

Step 4F-A was a no-POST retry preflight after the user reported adding the GMO
Foreign Exchange FX API key `Trade > Order` permission. This task did not retry
the order and did not issue an approval id or approval gate.

Sanitized environment and ledger checks:

```text
GMO_FX_API_KEY: set
GMO_FX_API_SECRET: set
ledger_exists: true
ledger_state: POST_COMPLETED
attempt_count: 1
post_started_present: true
post_finished_present: true
result_category: api_rejected
```

Because the ledger is already `POST_COMPLETED` with `attempt_count=1`, same-day
POST is still blocked. Step 4F-A did not reset, delete, edit, or overwrite the
ledger.

Sanitized read-only Private API checks:

```text
account/assets: success
open_positions_count: 0
active_orders_count: 0
raw_response_saved: false
raw_response_displayed: false
```

This read-only success confirms only that the read-only endpoints are reachable
with the current key environment. It does not prove that the order permission is
effective for a future POST.

Sanitized public rules and market snapshot:

```text
USD_JPY minOpenOrderSize: 100
USD_JPY sizeStep: 1
USD_JPY maxOrderSize: 500000
USD_JPY in TRY/ZAR/MXN 10000 exception set: false
service_status: OPEN
maintenance_active: false
bid: 161.789
ask: 161.794
spread_jpy: 0.005
ticker_age_seconds: 0.650
current_jst: 2026-06-25T14:54:16+0900 JST
```

Step 4F-A judgement:

```text
READY_FOR_LATER_4F_B
```

This means a later Step 4F-B may be considered only if all of the following are
true:

- it is a separate task with a fresh preflight
- it is a different day, or an explicitly reviewed new ledger policy is approved
- the user-side permission, IP restriction, account state, available margin, and
  required agreement checks are complete
- `account/assets`, `openPositions`, and `activeOrders` pass with sanitized
  output
- open positions and active orders are both 0
- USD_JPY public rules still allow 100 units
- market status is not maintenance and spread remains within the configured
  threshold
- the run is inside the project execution window, normally weekday
  10:00-14:30 JST
- Step 4F-B stops at a new approval gate before any POST

Step 4F-A does not authorize same-day retry or immediate execution.

## 13. Step 4F Approval Command Alignment

Step 4F-B was stopped during the pre-execution code review because the prompt
required the Step 4F approval command shape, but the runner still used the
older Step 4 approval shape:

- required by Step 4F-B: `STEP4F-` approval id prefix
- required by Step 4F-B: `ACK_ORDER_PERMISSION=YES`
- required by Step 4F-B: `ACK_IP_ACCOUNT_CHECK=YES`
- previous runner shape: `STEP4-` approval id prefix and no Step 4F-specific
  order-permission / IP-account ACK tokens

The runner and tests now align to the Step 4F-B approval command contract:

```text
STEP4_APPROVE <approval_id> SIDE=BUY SYMBOL=USD_JPY SIZE=100 ACK_RISK=YES ACK_OPEN_POSITION=YES ACK_API_SCOPE=YES ACK_ORDER_PERMISSION=YES ACK_IP_ACCOUNT_CHECK=YES ACK_NO_EVENT=YES ACK_NO_RETRY=YES ACK_NO_LOOP=YES ACK_NO_ADD=YES ACK_NO_CHANGE=YES ACK_NO_CANCEL=YES ACK_NO_CLOSE=YES ACK_STOP_ON_UNKNOWN=YES
```

For Step 4F-B, `<approval_id>` must use the `STEP4F-XXXXXXXX` form. The old
compact command without `ACK_ORDER_PERMISSION=YES` and
`ACK_IP_ACCOUNT_CHECK=YES` fails closed for Step 4F-B.

This approval alignment task did not perform:

- HTTP POST
- live order
- approval id issuance
- approval gate issuance
- fresh preflight or read-only connection
- ledger reset, delete, edit, or overwrite
- raw response display or storage
- credential, header, or signature value display

The next Step 4F-B attempt must be a separate task, start from fresh preflight,
and stop at the approval gate before any POST.
