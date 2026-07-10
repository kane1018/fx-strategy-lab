# H-11 Regime-Adaptive MoE — Staged Live Policy (no-POST)

Date: 2026-07-10
Applies to: `H-11_REGIME_ADAPTIVE_MOE_DIRECTIONAL_PROBABILITY`
Status: `DRAFT_INACTIVE`
Future live intent: `CONDITIONAL_STAGE2_SUPERVISED_LIVE`
Current stage: `PRE_STAGE1_SPEC_INCOMPLETE`

```text
frozen_spec=false
stage1_wiring_allowed=false
stage1_execution_allowed=false
paper_execution_allowed=false
stage2_allowed=false
stage2_execution_authorized=false
stage3_allowed=false
live_allowed=false
major_incident_resume_allowed=false
automatic_trade_authority=false
risk_gate_permission=false
kill_override_allowed=false
actual_entry_post_allowed=false
actual_settlement_post_allowed=false
actual_post=false
post_count=0
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```

本書は、H-11を将来の監督付きlive判断の**予定前提**とするoperator方針を記録する。
H-11が選定されたことや本書の存在は、現時点のpaper、live、API/broker、credential、POST権限を与えない。
H-11は全ての前提を後日満たした場合に限りStage 2で使用を検討する。1条件でも不足・不一致ならfail-closedで停止する。

## 1. 必須の順序

次の順序を省略・並行・事前承認してはならない。

1. H-11の全未決定項目をoperatorが確定し、完成したfrozen specと`config_hash`を別Stepで記録する。
2. 別途授権された`STAGE1_PAPER_WIRING_STEP`でのみ、fake-transport-onlyのStage 1配線を実装・検証する。
3. 別途授権されたStage 1 paper実行で、連続2週間以上かつ20 paper trades以上に加え、
   ACTIVE policy §5の規律違反0、予算・停止基準発火テスト、誠実なUNPROVEN採点条件を満たす。
4. operatorがStage 1の完全な結果、逸脱、停止事象、予測契約と実行契約の整合をreviewする。
5. 別の`STAGE2_SUPERVISED_LIVE_PROCEDURE_STEP`で、Stage 2手順を作成・承認する。
6. 2026-07-06重大インシデント後のlive再開について、別のmajor-incident resume policy Stepを完了する。
7. 各取引ごとにAGENTS.md Step 6G限定例外のfresh gateとoperator current-turn exact confirmationを満たす。

手順1では、ACTIVE policy §4の全項目と
[H-11 preregistration draft §8](STRATEGY_REGIME_ADAPTIVE_MOE_PREREGISTRATION_NO_POST_20260710.md)の
**全`PENDING_OPERATOR_DECISION` fieldを個別に解決**しなければならない。包括的な承認、空欄、暗黙値、
既定値で代替せず、全fieldの凍結値が揃うまで`frozen_spec=true`へ変更しない。

将来のStage 2 per-entry permissionは次のANDだけで構成する。

```text
stage2_qualified
AND budget_remaining
AND risk_gate_passed
AND kill=off
AND fresh_per_trade_current_turn_operator_confirmation
```

いずれかがfalseまたはunknownならblockし、permissionを生成しない。operator confirmationはbudget、risk gate、
killを上書きできず、過去confirmationも再利用できない。現在は`stage2_execution_authorized=false`、
`risk_gate_permission=false`、`kill_override_allowed=false`である。

Stage 1の期間・件数だけを満たしてもStage 2権限は発生しない。Stage 2手順やmajor-incident resumeを
本書で先行承認しない。E1 gateはStage 3+専用で、formal statusは
`E1_IMPLEMENTED_NOT_GATE_PASSED`のまま。本書はE1、E2、E3いずれのgateも通過させない。

## 2. Predictionと実行の分離

H-11研究層の許可出力は確率、expert weights、不確実性、prediction status、block reasonsだけであり、
直接POSTへ接続しない。

将来の別途授権されたinactive adapterは、適用される完成済みStage 1またはStage 2契約の下でのみ、次の決定論的構造で
既存の`AUTO_PREVIEW_SIGNAL_*`へ写像することを検討できる。

1. missing、invalid、nonfinite、out-of-domain、unsafe、unknownなら`AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED`。
2. frozen abstention、expert disagreement、uncertainty条件に該当すれば`AUTO_PREVIEW_SIGNAL_HOLD`。
3. eligibleかつ`p_up >= frozen_buy_probability_threshold`なら`AUTO_PREVIEW_SIGNAL_BUY`。
4. eligibleかつ`p_up <= frozen_sell_probability_threshold`なら`AUTO_PREVIEW_SIGNAL_SELL`。
5. eligibleかつ`p_up`がfrozen buy/sell thresholdの間なら`AUTO_PREVIEW_SIGNAL_HOLD`。

上記は安全block→abstention→direction thresholdの優先順で適用し、thresholdの順序・境界・toleranceが
不正または未凍結なら`AUTO_PREVIEW_SIGNAL_UNKNOWN_BLOCKED`とする。threshold、eligibility、abstention、
disagreement、uncertaintyの具体値はpreregistration §8の`PENDING_OPERATOR_DECISION`である。
adapterは現時点で未実装・inactiveであり、別途授権なしに有効化しない。
`AUTO_PREVIEW_SIGNAL_HOLD`はpreview adapterの非処方的出力で、operator専有の`HOLD`とは別物である。
adapterは`ENTRY_BUY`、`ENTRY_SELL`、operator `HOLD`を生成・推測・代行しない。previewはpermissionでも注文命令でもない。

[OPERATOR_PRE_TRADE_CAUTION_BRIEFING_DESIGN_NO_POST_20260709.md](OPERATOR_PRE_TRADE_CAUTION_BRIEFING_DESIGN_NO_POST_20260709.md)
の既存generatorはwarning-only、direction-free、confidence-freeのまま維持し、H-11出力を取り込まない。
H-11 adapterとcaution briefingを混同・直結しない。

## 3. 将来のentry境界（現在は無効）

- Stage 2 entryは次が全てtrueの場合にだけ検討できる。

  ```text
  stage2_qualified
  AND budget_remaining
  AND risk_gate_passed
  AND kill=off
  AND fresh_per_trade_current_turn_operator_confirmation
  ```

- いずれかがfalse/unknownならblockし、entry permissionを生成しない。operator confirmationはbudget、
  risk gate、killを上書きしない。`kill_override_allowed=false`を維持する。
- entryは独立した将来のStep 6G taskとする。
- taskごとにfresh preflight、fresh current-turn exact confirmationを要求する。
- entry POST attemptは最大1回。retry、repost、second POSTは禁止する。
- timeout、unknown、network/client/server errorでもattemptを消費する。
- 結果不明時は再送せず、新規entryをblockし、operatorへescalateする。
- prediction、preview、no-warning、過去のconfirmationはPOST permissionへ変換しない。
- operator専有のorder intentをモデルまたはagentが推測・変更しない。

## 4. 将来のsettlement境界（現在は無効）

- settlementはentryと別の将来Step 6G taskとし、entry承認を再利用しない。
- fresh settlement preflightと別のfresh current-turn exact confirmationを要求する。
- settlement POST attemptは最大1回。retry、repost、second POSTは禁止する。
- official dedicated settlement routeだけを使用する。
- generic close、generic opposite close、opposite prediction as closeは常にfalseとする。
- 反対方向のH-11予測をsettlement intentへ自動変換しない。
- timeout、unknown、network/client/server errorでもattemptを消費し、再送せずoperatorへescalateする。

## 5. Kill、dead-man、unknown result

- kill/dead-manは新規行動をblockする。自動close、auto settlement、POSTを発火しない。
- kill/dead-man発動時の建玉処理はoperator専有の別settlement taskに分離する。
- broker/API結果がunknownなら、新しいentryをblockし、照合と判断をoperatorへescalateする。
- unknownを成功・失敗・flatへ推測しない。attempt ledgerをreset、削除、書換えしない。
- safety vetoが1件でもあればStage昇格・entry・settlementを停止する。

## 6. 変更・監視・採点

- H-11のspec、router、expert、threshold、mapping、risk設定を稼働結果に応じて場当たり的に変えない。
- 変更はreview window、new version、new `config_hash`、必要な独立評価を要する。
- H-11の方向予測評価とStage 1/2の執行・risk scorekeepingを分離する。
- 実現損益や少数tradeを予測edge証明に使用しない。
- `performance_proof_status=false`、`live_ready=false`、`unattended_live_supported=false`を維持する。
- automatic/unattended liveは本書の対象外。Stage 3は別方針StepとE1 gateを必要とする。

## 7. Source of truthとfail-closed競合処理

適用順序は次とする。

1. `AGENTS.md`、default-deny hard guard、重大インシデント停止条件
2. ACTIVEな[operator-selected policy](OPERATOR_SELECTED_HYPOTHESIS_POLICY_REVISION_NO_POST.md)、特に§7安全不変条件
3. 本書（ただしStatusは`DRAFT_INACTIVE`）
4. [H-11 preregistration draft](STRATEGY_REGIME_ADAPTIVE_MOE_PREREGISTRATION_NO_POST_20260710.md)
5. registry、integrated state、project status、handoff
6. 過去のproductization、caution briefing、runbook（後日のnarrow precedence noteを含む）

上位文書との競合、同順位文書の曖昧さ、古いlive表現との不一致があれば、より厳しいno-execution側を採用する。
不明点を補完してStageやPOST権限を作らない。競合解消は別docs-only operator decision Stepで行う。

## 8. 現在の結論

operatorの方針は、H-11を将来liveの予定前提として段階的に育てることである。ただし現在は
`PRE_STAGE1_SPEC_INCOMPLETE`であり、本書は`DRAFT_INACTIVE`。次に許され得るのはH-11 spec freezeの
別docs-only Stepであり、Stage 1配線・実行、paper、Stage 2/3、major-incident resume、live、POSTではない。

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
private_api=false
public_api=false
public_get=false
data_fetch=false
credential_read=false
env_read=false
raw_request_response_access=false
raw_id_value_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
automatic_trade_authority=false
```
