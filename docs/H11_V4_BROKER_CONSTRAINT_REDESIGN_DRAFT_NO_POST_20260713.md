# H-11 v4 — Broker Constraint Redesign Draft（docs-only / no-POST）

Date: 2026-07-13

Status: **DRAFT_PENDING_OPERATOR_APPROVAL**

## 1. 位置付け

H-11 v4は、H-11 v3の凍結IFDOCO STOP profileを変更する作業ではない。v3がbroker回答により
安全条件を満たさないと判明したため、実行profileを未選定のまま制約から再設計する別versionである。

```text
supersedes_v3_config=false
v3_status=FROZEN_AND_BLOCKED_BY_BROKER_CONSTRAINTS
v4_execution_profile=NOT_SELECTED
v4_config_hash=NOT_ASSIGNED
actual_post=false
broker_read=false
broker_write=false
credential_read=false
data_fetch=false
live_ready=false
unattended_live_supported=false
```

## 2. v4で先に固定する非交渉条件

新しいexecution profileは、実装またはactual activationの前に、次の全条件を公式仕様または
operatorが取得した公式回答で満たす必要がある。

1. 未約定entryをsignal validity window以内に必ず失効させられる。
2. 部分約定が起きても、実約定量を超える保護注文を残さない。
3. 部分約定を検知するだけでなく、未保護・過剰保護・結果unknownをfail-closedで安全に扱える。
4. HEDGING環境でもgeneric opposite entryを決済代替に使わない。
5. entry、保護、必要な例外処理の各routeは、one-attempt・no retry/repost・結果unknown時HALTを維持する。
6. server-side損失限定、boot/post-event reconciliation、credential secrecy、dead-man、通知、
   budget stopを後退させない。

1つでも満たせなければ、v4のactual activationを設計・実装しない。

## 3. 現時点で選定しないもの

次は公式回答・独立安全レビューなしに採用しない。

- 固定30取引日expiryのIFDOCO STOP entry
- 部分約定後も指定sizeのまま残るOCO保護
- generic opposite orderによる解消
- 自動cancel、change、closeを既存v3へ追加する変更
- client-side監視だけでserver-side保護不足を補う方式

## 4. 次の公式確認事項（operator送信前の草案）

新profile候補を選ぶ前に、brokerへ次の事実を確認する。

1. IFDOCOを含む外国為替FX APIで、全量約定または未約定を保証する執行条件はあるか。
   利用可能な注文種別、time-in-force、条件、API fieldを公式名称で示してほしい。
2. request単位でsignal validity window以下のexpiryを指定できる公式API routeはあるか。
   ない場合、未約定entryを安全に失効させるbroker-native手段は何か。
3. 部分約定時に、第二OCO注文sizeが実建玉を超える場合、各OCO legが発火したときの正確な挙動は何か。
   反対建玉を新規に作る可能性、reject、余剰分の扱いを公式に確認する。
4. 部分約定後に保護sizeを実約定量へ安全に整合させる公式routeがあるか。
   cancel/change/settlementを要する場合、対象識別、冪等性、結果unknown時の扱いを公式仕様で確認する。
5. entryの実約定量に等しいserver-side SL/TPを原子的に作る公式order routeがあるか。

この問い合わせ自体はoperator専任であり、Codexは送信しない。回答はrawのまま保存せず、
safe aggregateだけを次のv4 reviewへ反映する。

## 5. v4の選定ゲート

```text
all_non_negotiable_conditions_confirmed
AND official_answer_supports_a_safe_execution_profile
AND v4_profile_selected_before_implementation
AND new_config_hash_assigned
AND independent_safety_review_clear
AND focused_fake_tests_clear
AND separate_operator_implementation_authorization
```

これらは将来のdocs-only設計またはno-POST実装の入口であり、actual activation、broker access、
credential access、POST、無人常駐を許可しない。

## 6. v4が不成立の場合

brokerが上記の安全なexecution profileを提供しない、または公式に確認できない場合、
H-11は実売買routeとして採用しない。v3/v4を無理にliveへ接続せず、研究・no-POST評価に留める。
