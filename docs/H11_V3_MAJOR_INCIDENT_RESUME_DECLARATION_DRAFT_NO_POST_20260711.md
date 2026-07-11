# H-11 v3 Major-Incident Resume Declaration — Draft（no-POST）

Date: 2026-07-11

Status: **DRAFT_NOT_DECLARED_NOT_EFFECTIVE**

Purpose: 2026-07-06に確認された実POST可能コードとcontrolled simulationの誤認リスクを踏まえ、
H-11 v3だけを将来resume検討する際のoperator宣言文を事前に固定する。

本書はresumeを宣言しない。actual activation、hard guard解除、Private API、credential、broker
read/write、POSTを許可しない。

## Operator declaration template

> 私は、2026-07-06重大インシデントの原因と、simulation/no-POSTラベルだけでは実送信不能を
> 保証できないことを理解した。H-11 v3の凍結済みconfigに限定し、下記の独立条件をすべて
> fresh evidenceで確認した場合にのみ、別途`H11_V3_ACTUAL_ACTIVATION_STEP`を開始する。
> 本宣言は他仮説、Step 6G、generic order/close/cancel/change、retry/repost/second POSTへ
> 適用しない。

Operator name: `PENDING_OPERATOR`

Declaration timestamp (JST): `PENDING_OPERATOR`

Approved config hash: `PENDING_OPERATOR_EXACT_MATCH`

Approved capability contract hash: `PENDING_OPERATOR_EXACT_MATCH`

## 宣言前の必須確認

1. actual senderの完全差分と到達可能routeがH-11 v3 IFDOCO一つに限定されている。
2. default-deny hard guardはenvや保存済みbooleanで解除できない。
3. generic allow bridgeが存在しない。
4. persistent intent/attempt、unknown halt、server-side OCO、reconciliation、sealed credential、
   dead-man、外部通知がfresh testsとfault evidenceでclear。
5. actual accountのpermission、pending expiry、partial-fill、lot/tick、ToS/feeがoperator確認済み。
6. clean tree、`HEAD == origin/main`、全test/ruff/diff-check/danger scan成功。
7. actual activationは別current-turnで明示承認し、過去の文言・test・safe labelを再利用しない。

## generic allow bridge禁止

次のような再利用可能な自動解除器は実装しない。

- 複数のsafe booleanを結合して`allow_real_broker_post=true`を返す関数
- 過去のconfirmationやtest結果からactivation tokenを自動生成する処理
- env、`.env`、state file、journal labelだけでhard guardを解除する処理
- H-11 v3以外でも再利用できる共通live allow helper

専用activation permissionはoperatorの記名resume宣言とfresh current-turn activation入力に
限定し、コード側で一般化しない。

## 現在の効力

```text
resume_declared=false
resume_effective=false
activation_token_constructible=false
generic_allow_bridge=false
actual_post=false
credential_read=false
broker_write=false
```
