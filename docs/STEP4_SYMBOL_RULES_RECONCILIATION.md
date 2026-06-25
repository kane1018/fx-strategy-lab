# Step 4 Symbol Rules Reconciliation

## 1. Purpose

This review resolves the Step 4 quantity mismatch before any live order retry.

Question:

```text
Is the current API minimum open order size for USD_JPY 100 units or 10000 units?
```

This is a specification reconciliation only. It does not execute HTTP POST,
place a live order, issue an approval id, create a ledger, select BUY / SELL, or
change the plan to 10000 units.

## 2. Previous Step 4A Stop Reason

Step 4A was stopped because the API docs response example showed:

```text
USD_JPY minOpenOrderSize = 10000
```

That appeared to conflict with the project Step 4 plan:

```text
USD_JPY 100 units, one-shot, manual approval only
```

The safe response is to reconcile current public rules before any Step 4 retry.

## 3. Sources Checked

Official and public sources checked:

- live public API: `GET https://forex-api.coin.z.com/public/v1/symbols`
- official product page: `https://coin.z.com/jp/corp/product/info/fx/api/`
- 2025-04-04 notice: `https://coin.z.com/jp/news/2025/04/14320/`
- 2025-09-25 notice: `https://coin.z.com/jp/news/2025/09/15045/`
- API docs: `https://api.coin.z.com/fxdocs/`

No Private API endpoint was called.

## 4. Live Public API Result

Sanitized extraction from `GET /public/v1/symbols`:

```text
[USD_JPY]
symbol: USD_JPY
minOpenOrderSize: 100
maxOrderSize: 500000
sizeStep: 1
takerFee: None
makerFee: None

[TRY_JPY]
symbol: TRY_JPY
minOpenOrderSize: 10000
maxOrderSize: 500000
sizeStep: 10

[ZAR_JPY]
symbol: ZAR_JPY
minOpenOrderSize: 10000
maxOrderSize: 500000
sizeStep: 10

[MXN_JPY]
symbol: MXN_JPY
minOpenOrderSize: 10000
maxOrderSize: 500000
sizeStep: 10
```

Interpretation:

- USD_JPY currently accepts `minOpenOrderSize=100`.
- `sizeStep=1` does not block a 100-unit order.
- TRY_JPY / ZAR_JPY / MXN_JPY are the 10000-unit exception set in the live
  public response.

Raw response was not saved and was not printed in full.

## 5. Official Product Page Result

The official Foreign Exchange FX API product page states that API minimum order
size is:

```text
new order 100 units / order
```

with this exception:

```text
TRY/JPY, ZAR/JPY, MXN/JPY are new order 10000 units / order
```

USD_JPY is not listed as an exception.

## 6. Official Notices Result

### 2025-04-04 Notice

The April 2025 notice announced that, after the 2025-04-26 regular maintenance,
the API minimum order size would change from:

```text
10000 units / order
```

to:

```text
100 units / order
```

At that time, TRY/JPY, ZAR/JPY, and MXN/JPY were excluded and remained 100000
units / order.

### 2025-09-25 Notice

The September 2025 notice announced a further change for only:

```text
TRY/JPY
ZAR/JPY
MXN/JPY
```

Those pairs changed from 100000 units / order to 10000 units / order. The same
notice states that pairs other than TRY/JPY, ZAR/JPY, and MXN/JPY can be traded
from 100 units / order.

USD_JPY is therefore in the 100-unit group.

## 7. API Docs Response Example Classification

The API docs `GET /public/v1/symbols` section shows a response example with:

```text
"symbol": "USD_JPY"
"minOpenOrderSize": "10000"
"responsetime": "2022-12-15T19:22:23.792Z"
```

This is classified as an old/static response example, not the current live
trading rule, because:

- the example response time is 2022-12-15
- the official 2025-04-04 notice changed the minimum order size after that date
- the official product page now states 100 units with only TRY/JPY, ZAR/JPY, and
  MXN/JPY as 10000-unit exceptions
- the live public API currently returns USD_JPY `minOpenOrderSize=100`

## 8. USD_JPY 100-Unit Step 4 Feasibility

Decision:

```text
READY_FOR_STEP4_RETRY
```

Reason:

- live public API returns USD_JPY `minOpenOrderSize=100`
- live public API returns USD_JPY `sizeStep=1`
- official product page states API new order minimum is 100 units, except
  TRY/JPY, ZAR/JPY, and MXN/JPY
- September 2025 notice states pairs other than TRY/JPY, ZAR/JPY, and MXN/JPY
  can be traded from 100 units / order
- API docs `10000` value is a 2022 response example and is superseded by later
  notices plus the current public API response

This decision only permits preparing a Step 4 retry task. It does not authorize
or execute a live order.

## 9. Explicit Non-Actions

This reconciliation did not:

- call Private API order endpoints
- execute HTTP POST
- place a live order
- issue an approval id
- create a one-shot ledger
- check API key values
- check secret values
- read `.env`
- select BUY or SELL
- change the plan to 10000 units

## 10. Next Work

If continuing, the next task may be Step 4A retry only:

1. Re-run Git clean and Step 4A preflight.
2. Re-check API key / secret presence as set / missing only.
3. Re-run sanitized read-only Private API checks.
4. Re-run focused tests and ruff.
5. Stop at the exact approval gate.

Step 4B live order must still be a separate task and requires the exact user
approval phrase with BUY or SELL selected by the user.

## 11. Step 4B Preparation Implementation Boundary

Step 4B preparation added a one-shot live runner boundary after this symbol
rules reconciliation:

- live outbound body allowlist:
  `symbol`, `side`, `size`, `clientOrderId`, `executionType`
- fixed live order values: `USD_JPY`, `size="100"`, `executionType=MARKET`
- approval command exact match for BUY or SELL, with 300-second expiry
  (`elapsed_seconds <= 300` passes, `elapsed_seconds > 300` fails)
- the earlier long Japanese approval phrase is retired/deprecated; Step 4 now
  uses a compact one-line ASCII command:
  `STEP4_APPROVE <approval_id> SIDE=BUY|SELL SYMBOL=USD_JPY SIZE=100 ACK_...=YES`
- all ACK tokens for risk, open-position risk, API scope, no-event confirmation,
  no retry, no loop, no additional order, no change, no cancel, no close, and
  stop-on-unknown are required; missing ACKs, non-`YES` values, extra tokens,
  newlines, extra spaces, and the old Japanese phrase fail closed
- persistent one-shot ledger for PREPARED / POST_STARTED / POST_COMPLETED /
  RESULT_UNKNOWN / EXPIRED states
- fake transport tests for one POST attempt, timeout -> RESULT_UNKNOWN,
  no retry, no loop, and no raw artifact persistence
- the previous 120-second fixed approval window is retired; approval after the
  exact phrase still requires a fresh post-approval preflight, and the final
  dynamic preflight-to-POST window remains within 30 seconds

The preparation does not execute HTTP POST, place a live order, choose BUY or
SELL, cancel or close orders, or perform real-money verification. Step 4B live
execution remains a separate task and requires a fresh exact approval command.

## 12. Step 4D API Reject Follow-up

After the one-shot Step 4B-B attempt returned sanitized
`transport_result=api_rejected`, Step 4D added a local-only reject
classification model and API permission / account / IP settings checklist.

Because no raw response or raw error code is used, the current judgement is:

```text
REJECT_CAUSE_PARTIAL
```

Step 4D does not authorize a retry. It does not execute HTTP POST, issue an
approval id, choose BUY / SELL, reset the ledger, display raw response, or touch
credential values. Future work should first complete the user-side API
permission checklist before any separate Step 4 retry preflight.
