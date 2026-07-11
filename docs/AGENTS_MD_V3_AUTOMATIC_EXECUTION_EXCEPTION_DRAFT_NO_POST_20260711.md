# AGENTS.md H-11 v3 Automatic Execution Exception — Draft（no-POST）

Date: 2026-07-11

Status: **DRAFT_NOT_EFFECTIVE**

この文書は`AGENTS.md`本体へ将来追加する場合の条文案であり、現時点では効力を持たない。
`AGENTS.md`本体は変更していない。actual POST、Private API、credential、broker read/write、
自動執行を許可しない。

## 条文案

### H-11 v3 observed unattended live限定例外

通常作業では、Private API、APIキー、実注文、実資金、残高・建玉・注文照会、HTTP POST、
broker/order endpoint、実credentialを引き続き禁止する。

ただし、operatorが別途`H11_V3_ACTUAL_ACTIVATION_STEP`を明示的に依頼し、次の全条件を
同一Step内で確認・承認した場合に限り、H-11 v3の凍結済みIFDOCO経路へ限定した自動執行例外を
発効できる。

1. H-11 v3 config hashとcapability contract hashが凍結値に一致する。
2. clean working tree、`HEAD == origin/main`、全検証成功、未解決safety vetoなし。
3. broker-native pending expiry、actual account mode、最小lot、tick、API permission、IP制約、
   partial-fill観測可能性が確認済み。
4. server-side OCO損失限定、persistent one-attempt ledger、unknown-result halt、
   boot/post-entry reconciliation、dead-man、外部通知がactivation reviewを通過する。
5. sealed credential提供方式が値非露出・ログ/Git非保存で承認済み。
6. 2026-07-06重大インシデントに対するH-11 v3限定resume宣言がoperator記名で発効済み。
7. operatorがactual activationのcurrent-turn確認文を完全一致で入力する。

### per-trade confirmation除去の限定範囲

上記例外が発効したH-11 v3の凍結configに限り、各entry前のoperator current-turn確認を
自動執行の成立条件から外せる。これはoperatorの目視監視を禁止せず、目視を安全成立条件にも
しない。

この除去は次へ適用しない。

- H-11 v3以外の仮説・戦略・config hash
- Step 6G Controlled one-shot POST
- generic order、generic close、cancel、change、手動決済
- 凍結spec、size、budget、threshold、stop条件を変更した新version
- retry、repost、second POST

H-11 v3以外では、既存`AGENTS.md`とStep 6G限定例外をそのまま適用する。

### H-11 v3発効後も維持する強制条件

- 10,000通貨固定、最大1 entry/日、月間損失上限50,000円。
- entryは保護legを同時に含む公式IFDOCO routeだけを使用する。
- intentとattemptをPOST前に永続化し、同一日・同一intentのsecond attemptを拒否する。
- timeout、unknown、network/client/server error後はretry/repostせずHALTする。
- settlementはbroker-native OCOまたは承認済み公式専用routeだけを使用する。
- generic close、反対新規による決済、cancel/change経路を追加しない。
- 起動時とentry後はreconciliation-firstとし、不一致・不明なら新規entryを止める。
- credential、raw request/response、header、signature、token、ID、価格、PnLをログ・Git・報告へ
  出さない。
- stop、kill、dead-man、notification failure後は自動再開しない。

### hard guardと重大インシデント境界

safe boolean群をANDしてhard guardを解除するgeneric allow bridgeは作らない。H-11 v3の
activation permissionは、operator記名の重大インシデントresume宣言と同一turnの専用activation
入力からのみ得る。過去confirmation、safe label、test結果をpermissionとして再利用しない。

## 現在の効力

```text
draft_only=true
agents_md_modified=false
exception_effective=false
per_trade_confirmation_removed=false
actual_post=false
credential_read=false
broker_write=false
```
