# Step 6G GMO FX Official Rules Alignment

This document records the official-reference alignment for Step 6G close
settlement handling.

## Authoritative References

```text
GMO FX operation manual:
https://coin.z.com/corp_imgs/manual/kawasefx-trading-manual.pdf

GMO FX trading rules:
https://coin.z.com/jp/corp/product/info/fx/#rule
```

These are treated as authoritative for GMO Coin foreign exchange FX behavior.

## Alignment Decision

The project now treats buy-side and sell-side positions as able to coexist.
They must not be netted by Codex route logic.

Safe implementation decisions:

```text
generic_opposite_order_as_close_forbidden=true
generic_close_primitive_revoked=true
official_settlement_route_confirmed=false
actual_close_post_allowed_now=false
close_execution_blocked_reason=OFFICIAL_SETTLEMENT_ROUTE_NOT_CONFIRMED
```

The broker manual describes settlement as a distinct flow from position
summary/list controls. The trading rules describe hedged trading and
non-netting of buy/sell position quantities. Therefore a generic opposite
order must not be accepted as proof of settlement.

## Required Future Work

Before any future actual close POST can be considered, a separate no-POST
review must identify the official GMO settlement route and represent it as a
close-specific primitive with all required safe conditions.

Until then:

```text
actual close POST=false
close retry=false
close repost=false
second close=false
entry POST=false
ledger update=false
receipt handoff=false
raw/ID/value exposure=false
```

## Safety Boundary

This alignment document does not contain raw request/response data, broker/API
responses, account/order/transaction/position/trade IDs, credential values,
signature values, header values, actual market prices, or PnL values.
