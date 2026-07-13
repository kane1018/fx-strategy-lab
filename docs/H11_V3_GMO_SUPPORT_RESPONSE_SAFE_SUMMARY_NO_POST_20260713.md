# H-11 v3 — GMOサポート回答の安全要約（no-POST）

Date: 2026-07-13

Status: **OPERATOR_REPORTED_OFFICIAL_RESPONSE_SAFE_SUMMARY**

## 1. 目的と記録境界

operatorが共有したGMOコインサポート回答について、H-11 v3の設計判断に必要な
事実だけを安全に要約する。回答原文、問い合わせ番号、個人情報、口座情報、API key、
order/execution/position ID、raw request/responseは保存しない。

この文書はAPI接続、broker read/write、credential read、実POST、注文、cancel/changeを
許可しない。

## 2. 安全な事実要約

```text
pending_order_expiry=FIXED_30_TRADING_DAYS
expiry_request_parameter=NOT_AVAILABLE_FOR_IFOORDER
expiry_varies_by_order_type_or_symbol=false

partial_fill_can_occur=true
second_oco_size_auto_adjusts_to_executed_size=false
partial_fill_detectable_via_orderExecutedSize=true

hedging_configuration=SUPPORTED_IN_SPEED_ORDER_SETTINGS
```

`hedging_configuration`はSpeed Order設定についての回答であり、API実行時の建玉・決済
semanticsを単独で保証するものではない。H-11 v3では引き続きgeneric opposite closeを
禁止する。

## 3. v3への判定

### 3.1 Pending expiry

v3は未約定STOP entryが短期signalの有効期間を越えて約定しないことを必要とする。
しかし、brokerの固定30取引日expiryはrequestごとに短縮できず、v3にはauto-cancelがない。
したがってこれは`CONFIRMED_WITHIN_SIGNAL_WINDOW`に分類できない。

```text
v3_pending_expiry_status=EXCEEDS_SIGNAL_WINDOW
v3_actual_activation=false
```

### 3.2 Partial fill

部分約定を検知できても、第二OCO注文のsizeが実約定量と自動整合しない。検知は約定後であり、
v3には不一致を安全に是正する専用routeが凍結されていない。

```text
v3_partial_fill_status=PROTECTION_SIZE_MISMATCH_RISK
v3_actual_activation=false
```

## 4. 結論

```text
v3_safety_veto=true
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
credential_read=false
live_ready=false
unattended_live_supported=false
```

v3の凍結specを変更してこの問題を埋めない。次の検討は
[H-11 v4 broker constraint redesign draft](H11_V4_BROKER_CONSTRAINT_REDESIGN_DRAFT_NO_POST_20260713.md)
でのみ行う。
