# H-11 v4 Major-Incident Resume Declaration（draft / no-POST）

Date: 2026-07-15

Status: `DRAFT_INACTIVE_NOT_APPROVED_NOT_EFFECTIVE`

## 1. Purpose

2026-07-06重大インシデント監査後のH-11 v4に限定し、将来のresume判断で必要な宣言内容を先に固定する。
本書はresume、activation、broker access、credential access、POSTを許可しない。

## 2. Scope

```text
applies_only_to=H11_V4_GMO_MARKET_THEN_EXACT_OCO_NO_POST_V1
applies_to_v3=false
applies_to_manual_signal_ui=false
applies_to_step_6g=false
generic_allow_bridge=false
persistent_allowed_for_live=false
```

他version、他仮説、汎用broker transportへ流用できるboolean bridge、token factory、automatic permit builderを
作ってはならない。resumeはfresh evidenceとoperatorのcurrent decisionを必要とする。

## 3. Preconditions before effectuation

- working tree clean、HEAD == origin/main。
- v4 frozen profile、signal config hash、generation manifestのexact一致。
- focused/related/full safety test、ruff、diff check、danger scanが全て成功。
- actual Keychain itemのminimum permissionとpresenceを値非表示で確認。
- actual Pushover receipt/ackとemail secondary deliveryをsanitized確認。
- actual read-only reconciliationとaccount exclusivityをsanitized確認。
- current host fault rehearsal全項目合格。
- duplicate attempt、unknown halt、exact-size protection、15秒上限、risk/dead-manの独立レビューclear。
- crash後はpending attemptとfresh 3-GETで実状態を分類し、HALTを維持したままMARKET再送を禁止する。
- 部分約定の残entryが存在する間はOCO保護を許可せず、cancel後のfresh reconciliationで
  pending 0とactual filled sizeを確定する。
- frozen ATR、exact OCO plan digest、MARKET attempt timestampが同一generationへ永続bindingされている。
- planned lossがfrozen ATR stop幅＋0.1 pip tick丸め allowance＋5.0 pips adverse-slippage仮定で
  5,000円以下である。ただしMARKET gapの
  上限保証ではないことをoperatorが受け入れる。
- unowned position/orderなし、manual/private client停止、account flatのfresh確認。
- current generation／cycle／signalへ結合したflat preflightが2秒以内で、active/unowned countが全て0。
- MARKET side/size/cycleのpersisted intent exact-match、DB再照合one-use authorization、executor所有の
  monotonic 15秒clock、transport直前dead-man再確認が独立レビューclear。
- completed preparation evidenceはgeneration単位の永続one-useであり、別coordinatorまたはprocess再起動から
  同じgenerationへ再利用できない。
- v4 generation-bound entry-time gateは、月〜木のJST 5〜8時、金曜09:00未満／21:00以降、土日を
  MARKET直前に拒否する。
- 通常は最大保有82,800秒（23時間）、金曜entryは通常期限と土曜03:45 JSTの早い方をexit-sequence
  startとし、土曜04:00 JSTをflat目標とする。開始期限到達時の出口は、exact OCO取消、fresh reconciliation、
  position-specific time exitの単発固定順序であり、到達前には実行できない。04:00時点でflatを
  確認できない場合は自動再試行せずpersistent HALTする。この宣言を発効する前に、03:45自動dispatcherと
  04:00 target monitorが実装・独立review clearでなければならない。
- time exitのOCO取消transport直前とposition-specific time exit transport直前は、
  executor-owned monotonic clockで最大2秒以内の公式public status `OPEN` evidenceを、
  それぞれ別のone-use evidenceとして消費する。
  OCO取消前にOPENを確認できない場合はOCOを維持したままpersistent HALTとする。
  OCO取消後の決済前に確認できない場合はclose transportを行わずpersistent HALTとする。
- owned close executionのrealized PnLはfresh flat／expected size一致時だけcycle単位でexactly once
  persistent risk ledgerへ反映される。
- operatorがv4専用resume宣言をcurrent turnで明示承認。

1つでも不明または不一致なら発効せず、actual POST 0のまま停止する。

## 4. Initial canary evidence exception

2026-07-16 operator承認により、初回の監視付きcanaryに限り、actual OCO rowsと15秒以内の
exact-size protection成立をそのcanaryで収集してよい。これは事前証拠の省略ではなく、初回canaryを
唯一のactual behavior proofとする限定ルールである。

```text
applies_only_to_initial_supervised_canary=true
maximum_entries=1
quantity_units=10000
maximum_unprotected_seconds=15
second_live_cycle_allowed_before_clear_proof=false
same_action_retry=false
same_action_repost=false
unknown_halts=true
```

canary後に次のいずれかが不明または不一致なら、宣言は発効せず、第2 live cycleを禁止する。

- actual activeOrders OCO rowsがowned protectionとしてsanitized識別できる。
- protection sizeがactual filled sizeとexact matchする。
- entry fillからprotection confirmationまで15秒以内である。
- duplicate attempt、retry、repost、raw/ID/secret exposureが0である。
- journal、risk、dead-man、notification、reconciliationがclearである。

本例外はactual activation permitを生成しない。実Keychain、actual notification、Private GET、POST、
AGENTS.mdのactual v4例外は、引き続き別Stepの明示授権を必要とする。

## 5. Future declaration text

次の文は上記preconditionが別Stepで確認されるまで入力・適用しない。

```text
I APPROVE H11 V4 MAJOR INCIDENT RESUME FOR THIS REVIEWED GENERATION ONLY
```

この文の一致だけでactivation permitを生成してはならない。fresh gate、独立レビュー、別actual activation Stepを
追加で必要とする。

## 6. Current state

```text
declaration_approved=false
declaration_effective=false
initial_canary_evidence_policy_approved=true
activation_permit_issued=false
actual_post=false
broker_read=false
broker_write=false
credential_read=false
live_ready=false
unattended_live_supported=false
```

## 7. Actual activation preparation authorization record（2026-07-16）

OperatorはKeychain値非表示確認、Pushover/email実配送、3経路のPrivate GET、非破壊host/KILL試験、
独立レビューまでを承認した。ただしcanary broker POST直前で停止し、fresh最終確認を提示する。

この授権によりAGENTS.mdへv4準備限定例外を追加したが、本resume宣言そのものは引き続きdraft/inactiveである。
準備証拠をactivation permitへ変換するgeneric allow bridgeは作らない。commit/pushは別授権である。

準備証拠はpersistent one-shot ledgerで固定順序を強制する。SMTP provider acceptanceだけではemail deliveryを
clearにせず、operatorのexact receipt confirmationを別段階で必要とする。G010以降はopenPositions／activeOrdersの
symbolを省略した口座全体snapshotとoperator account-exclusivity confirmationを別の事実として保持し、
両者をgeneric activation booleanへ統合しない。準備snapshotは2秒以内のcanary preflight clearではない。

```text
preparation_authorized=true
resume_declaration_approved=false
resume_declaration_effective=false
broker_post_authorized=false
activation_permit_issued=false
```
