# H-11 v3 — IFDOCO Protected Execution Profile Spec Freeze（no-POST）

Date: 2026-07-11

Hypothesis ID: `H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY`（version 3）

Status: **FROZEN_NO_POST_IMPLEMENTATION_AUTHORIZED**

Operator decision: 収益性の事前観測期間を短縮し、極小額liveで並行収集する。安全条件はlive前に省略しない。

```text
config_hash=sha256:737765dcbed89befceef8660d2b362c834344cc7e36e139d2ff75984914c3262
capability_contract_hash=sha256:8dd4c936e6cde8b5b9ac132cf68e9a7f4eecea2224a87a0d3864cd4c95aa9d7e
prediction_model=H-11 v2 TREND_CONTINUATION_SINGLE_EXPERT（変更なし）
execution_profile=H-11 v3 IFDOCO_PROTECTED_ENTRY（新規）
actual_post=false
entry_post=false
settlement_post=false
post_count=0
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```

## 1. v3の位置付け

v3はv2の予測モデルを再学習・再調整しない。変更対象はexecution contractだけである。
通常MARKET entryはserver-side SL/TPを同一requestで付帯できないため使用せず、公開仕様上
entryとOCO保護を一つの親注文として表現できる`POST /private/v1/ifoOrder`を採用する。

公開仕様参照: [GMOコイン 外国為替FX APIドキュメント](https://api.coin.z.com/fxdocs/)
（2026-07-11閲覧。公開ページのみ。actual API call、credential確認、POSTは未実施）。

v2とv3の成績は混合しない。execution semanticsの変更なので新config hashの別実験とする。

## 2. 凍結値

| 項目 | v3凍結値 |
|---|---|
| prediction model | v2 TREND単独expert |
| v2 model config | `sha256:483fa9e4cc094251c3b3bfc5daaa007242a3385ba41c57caa95e5106fa4c4af3` |
| entry route | `POST /private/v1/ifoOrder` |
| order type | `IFDOCO` |
| first execution type | `STOP` |
| entry trigger | signal reference closeから継続方向へ`0.10 × ATR(24)` |
| stop loss | entryから逆方向へ`1.50 × ATR(24)` |
| take profit | `1.50R` |
| position size | `10,000` units |
| symbol capability | `USD_JPY` only |
| public minimum / step / tick | `10000` / `1` / `0.001` |
| max entries/day | `1` |
| max open positions | `1` |
| operator observation | 必須。ただしexecution gateではない |
| per-trade confirmation | 不要（actual activation後のみ） |
| server-side OCO | 必須 |
| retry / repost | false / false |
| second entry POST | false |
| unknown result | HALT |
| stop後の自動再開 | false |
| automatic cancel | false |

価格はcapability contractの`0.001`へ決定論的に丸める。symbol、tick、minimum lotが不一致なら
plan生成前に拒否する。actual activation時はfresh public symbolsとactual account permissionを
照合し、公開仕様が変わっていればv3を停止して新versionで再登録する。

## 3. Pending order expiry条件

IFDOCOの一次STOPが未約定で残留すると、signal validityを超えて約定する危険がある。そのため
`broker_native_pending_expiry_required=true`を凍結する。

- 公開仕様または安全なruntime確認でbroker-native expiryを確定できない場合、v3 actual activationは拒否する。
- 自動cancel routeはv3に含めない。
- cancelを追加する場合はv4・新config hash・別安全レビューとする。
- expiry確認前に「おそらく当日失効」と推測してliveへ進めない。

## 4. Live前の非交渉条件

以下は収益性の観測期間と交換しない。

1. IFDOCOが対象pair・10,000 units・price incrementで利用可能。
2. entry、TP、SLの3 legが同一親注文としてbroker側に存在することをsafeにreconcile可能。
3. pending entryのbroker-native expiryが確定。
4. persistent process lockとintent-first journalが有効。
5. boot時にposition / active orderをreconcileし、unknownならHALT。
6. entry attemptと独立settlement attemptは各1回まで。timeoutを含めattempt消費。
7. credentialはsealed boundary内のみ。値、長さ、hash、fingerprint、先頭末尾を露出しない。
8. raw request/response、order/execution/position/client IDを画面・docs・Gitへ出さない。
9. budget、kill、dead-man、通知、自動再開禁止がコードで強制。
10. actual transport bindingは別`H11_V3_ACTUAL_ACTIVATION_STEP`の明示授権まで存在させない。

## 5. 今回の実装許可と停止点

許可済み:

- 方針・仕様docs
- pure IFDOCO request builder
- deterministic v3 candidate builder
- persistent safe-label state machine / process lock / attempt counter
- fake transport lifecycle / fault tests
- focused/related tests、ruff、diff check、danger scan

未許可:

- broker/Public/Private APIアクセス
- credential/env読取
- actual sender binding / hard-guard解除
- actual POST、entry、settlement、cancel、change
- resident process / cron
- commit / push

## 6. 誠実な状態表示

```text
registry_status=OPERATOR_SELECTED_UNPROVEN
live_purpose=ENGINEERING_BURN_IN（将来のactual activation後）
edge_validated=false
profit_guaranteed=false
performance_proof_status=false
actual_post=false
unattended_live_supported=false
```
