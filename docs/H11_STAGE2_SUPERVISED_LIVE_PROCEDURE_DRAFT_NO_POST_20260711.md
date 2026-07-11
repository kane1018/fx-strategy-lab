# H-11 v2 Stage 2 Supervised Live Procedure — Draft Only (no-POST)

Date: 2026-07-11
Step: `STAGE2_SUPERVISED_LIVE_PROCEDURE_STEP`
Status: **DRAFT_ONLY_NOT_AUTHORIZED**
Applies to config: `sha256:483fa9e4cc094251c3b3bfc5daaa007242a3385ba41c57caa95e5106fa4c4af3`

> **Superseded for v3 (2026-07-11):** 本書はv2履歴draftとして保持する。v3は
> [H-11 v3 policy](H11_V3_OBSERVED_UNATTENDED_LIVE_POLICY_NO_POST_20260711.md)と
> [v3 freeze](STRATEGY_H11_V3_IFDOCO_SPEC_FREEZE_NO_POST_20260711.md)に従う。
> 本書・後発文書とも、別actual activation前のlive/POSTを許可しない。

本書は将来のoperator review用草案である。Stage 2の実装、有効化、broker/API接続、credential/env読取、
Private API、実POSTを許可しない。H-11 v2 Stage 1は実行中だが、Stage 2資格は未成立である。

```text
stage1_review_passed=false
api_capability_sheet_complete=false
major_incident_resume_policy_approved=false
stage2_procedure_authorized=false
stage2_execution_authorized=false
actual_post=false
entry_post=false
settlement_post=false
post_count=0
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```

## 1. 正となる文書と現行状態

1. [AGENTS.md](../AGENTS.md) の安全規則とStep 6G限定例外
2. [H-11 v2 spec freeze](STRATEGY_H11_V2_TREND_SINGLE_EXPERT_SPEC_FREEZE_NO_POST_20260711.md)
3. [Stage 1配線・開始記録](H11_STAGE1_PAPER_WIRING_NO_POST_20260711.md)
4. [ACTIVE operator-selected policy](OPERATOR_SELECTED_HYPOTHESIS_POLICY_REVISION_NO_POST.md)
5. [general staged-live policy](REGIME_ADAPTIVE_MOE_STAGED_LIVE_POLICY_NO_POST_20260710.md)

v2 specとStage 1開始記録が、旧`PRE_STAGE1_SPEC_INCOMPLETE`表記より後発かつH-11 v2固有である。
それでも本書が`DRAFT_ONLY_NOT_AUTHORIZED`である間は実行source of truthにならず、競合時は
より厳しいno-execution側を採用する。

## 2. DraftをACTIVE候補にできる必要条件

以下3条件を全て満たし、operatorが別Stepで明示授権するまで本草案を実装・有効化しない。

1. Stage 1を連続2週間以上かつ20 paper trades以上、規律違反0で完走し、operator reviewが合格。
2. `API_CAPABILITY_SHEET_SANITIZED_NO_POST.md`のoperator記入が完了。特にentryへのserver-side
   SL/TP付帯可否をunknownのままにしない。
3. 2026-07-06重大インシデントに対する専用resume policy Stepがoperator承認済み。

良い損益、予測確率、勝率、warning不在は上記条件を代替しない。H-11 v2は
`OPERATOR_SELECTED_UNPROVEN`のままで、`VALIDATED`へ自動昇格しない。

## 3. 将来のper-entry operator flow（現在は無効）

各entryは独立したStep 6G taskとし、次を順番に全て満たす場合だけ最大1 attemptを検討する。

```text
stage2_qualified
AND budget_remaining
AND risk_gate_passed
AND kill=off
AND model_status_eligible
AND fresh_per_trade_operator_current_turn_confirmation
```

- 1条件でもfalse/unknownならblockし、POST permissionを作らない。
- operator confirmationはbudget、risk gate、kill、model statusを上書きしない。
- H-11予測、preview、過去confirmation、過去の成功はpermissionとして再利用しない。
- symbol、side、size、executionTypeはoperatorがfreshに指定し、agent/modelは推測・変更しない。
- entry POST attemptは最大1回。timeout、unknown、network/client/server errorでもattemptを消費する。
- retry、repost、second POSTは禁止。結果不明時は再送せず、新規entryをblockしてoperatorへ報告する。
- raw request/response、header、signature、credential、order/execution/position IDは表示・保存しない。

## 4. 将来のsettlement flow（entryと別Step・現在は無効）

- settlementはentryと別のStep 6G task、別fresh preflight、別current-turn confirmationとする。
- settlement POST attemptは最大1回。retry、repost、second POSTは禁止する。
- official dedicated settlement routeだけを使用する。
- generic close、generic opposite close、反対予測をsettlementへ変換する経路は禁止する。
- timeout/unknown/errorはattemptを消費する。再送せず、新規entryをblockし、operatorへ報告する。
- kill/dead-manは新規actionをblockするだけで、自動settlement、自動close、POSTを発火しない。

## 5. Preview、caution briefing、operator判断の分離

- H-11 v2予測は凍結済みpreview adapterで`AUTO_PREVIEW_SIGNAL_*`までを生成する。
- previewは注文命令、operator判断、actual-POST permissionではない。
- `ENTRY_BUY` / `ENTRY_SELL` / `HOLD`、actual-POST承認、manual settlementはoperator専有。
- 既存caution briefingはwarning-only、direction-free、confidence-freeのままH-11出力を取り込まない。
- prediction/previewからorder payloadまたはPOSTへの直結経路を作らない。

## 6. 予算、停止、再開

- v2 `config_hash`に固定された月間・日次・1trade・連敗・1日trade数上限を変更しない。
- 勝ち・高いconfidence・Stage 1良績を理由にsizeまたは予算を増額しない。
- daily stopは契約どおり翌日解除。monthly/consecutive stopはoperator reloadだけとする。
- 同月内reload、冷却14日未満reloadは拒否する。post-mortemとreview window承認を必須とする。
- spec、threshold、予算、停止基準の変更はv3・新`config_hash`として別登録する。
- model health、budget、risk、kill、operator presenceのいずれかがunknownなら新規entryを停止する。

## 7. 監視・記録・停止

- Stage 2手順を将来有効化する場合も、常駐・cronはStage 3方針Stepまで禁止する。
- prediction、candidate、operator decision、attempt、unknown、stopを分離してsafe label/countだけ記録する。
- raw価格、個別PnL、broker response、ID、credentialをdocs/gitへ保存しない。
- stop、unknown、規律違反、reconcile不一致があれば自動再開しない。
- `performance_proof_status=false` / `live_ready=false` / `unattended_live_supported=false`を維持する。

## 8. 未解決operator項目（草案のまま保持）

- API能力表、特にserver-side SL/TP付帯可否
- major-incident resume policyの承認
- Stage 1完走後reviewの合否
- Stage 2の監視・通知・operator-presence/dead-man手順
- runtime safe readの必要範囲と回数（AGENTS.md限定例外を超えないこと）
- entry/settlementのsanitized reconciliation項目
- 本草案をACTIVE候補へ移すか否か

## 9. 現在の停止点

次に行えるのはStage 1の平日手動run、週次safe-aggregate review、API能力表とresume policyの
operator作業だけである。本草案からコード実装、broker/API/env/credentialアクセス、live、POSTへ進まない。

```text
actual_post=false
entry_post=false
settlement_post=false
post_count=0
broker_read=false
broker_write=false
credential_read=false
env_read=false
raw_request_response_access=false
raw_id_value_exposure=false
performance_proof_status=false
live_ready=false
unattended_live_supported=false
```
