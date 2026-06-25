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
