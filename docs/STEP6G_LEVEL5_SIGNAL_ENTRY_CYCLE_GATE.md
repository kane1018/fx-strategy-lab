# Step 6G Level 5 Signal Entry Cycle Gate

This document records
`Step 6G-PC-OX-R-LEVEL5-SIGNAL-ENTRY-CYCLE-GATE-C`.

## Runtime Premise

The previous runtime safe read check returned safe status/count only:

```text
position_status=NO_POSITION
position_count_safe=0
new_entry_allowed=true
close_planning_allowed=false
close_execution_allowed_now=false
```

No raw position object, broker/API response, ID, actual market value,
credential value, signature value, header value, ledger update, or receipt
handoff is used by this signal gate.

## Signal MVP Gate

The Level 5 signal MVP now accepts safe label inputs:

```text
trend_label=UPTREND / DOWNTREND / FLAT / UNKNOWN
volatility_label=NORMAL / HIGH / UNKNOWN
spread_label=NORMAL / WIDE / UNKNOWN
time_market_label=OK / BLOCKED / UNKNOWN
position_status=NO_POSITION / ONE_POSITION_OPEN / UNKNOWN / BLOCKED
```

Planning rules:

- `NO_POSITION + UPTREND + NORMAL spread + OK market -> ENTRY_BUY`
- `NO_POSITION + DOWNTREND + NORMAL spread + OK market -> ENTRY_SELL`
- `NO_POSITION + FLAT -> HOLD`
- unknown trend, wide/unknown spread, blocked/unknown market, high/unknown
  volatility, or non-`NO_POSITION` entry signal -> `BLOCKED`

Signals never directly execute POST and never expose raw market data or actual
market values.

## Entry Planning Gate

Entry planning is allowed only when:

```text
position_status=NO_POSITION
signal_checked=true
signal_type=ENTRY_BUY / ENTRY_SELL
entry_units_fixed=100
entry_symbol_safe_label=USD_JPY
entry_order_type_safe_label=MARKET
```

The gate is planning-only:

```text
entry_execution_allowed_now=false
entry_execution_step_may_be_planned=true/false
entry_requires_new_confirmation=true
entry_requires_time_market_operator_gate=true
entry_retry_allowed=false
entry_second_post_allowed=false
entry_raw_exposure=false
entry_id_exposure=false
```

This is not entry execution permission.

## Level 5 Cycle

The Level 5 cycle now has a planning-only state:

```text
IDLE + NO_POSITION + ENTRY_BUY/ENTRY_SELL -> ENTRY_READY
IDLE + NO_POSITION + HOLD -> IDLE
IDLE + position unknown/open/multiple -> HALTED or blocked
ENTRY_READY does not execute POST
ENTRY_SENT is not reached without a separate execution gate
```

## Next Step

If a safe injected snapshot produces `ENTRY_BUY` or `ENTRY_SELL`, the next
bounded step is:

```text
Step 6G-PC-OX-R-ENTRY-ORDER-EXECUTION-GATE-C
```

That step must require a fresh separate confirmation and must continue to
prohibit retry/repost, second POST, close POST, ledger update, receipt handoff,
raw/ID/value exposure, credential/signature/header exposure, and `.env` access.
