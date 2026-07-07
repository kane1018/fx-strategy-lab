# Entry Actual Final Preflight Checklist（no-POST・実行許可ではない）

本書は、将来の actual entry POST Step の**直前に必ず全項目を再確認する**ための
チェックリストである。本書のどの項目が満たされても、**actual POST / entry POST /
settlement POST の許可にはならない**。実行許可は、別Stepでの operator current-turn
exact confirmation と、そのStep固有の fresh gate 通過によってのみ扱われる。

実装モデル: `backend/app/services/gmo_live_entry_final_preflight.py`
（`build_gmo_entry_final_preflight_package`、default-deny・`__bool__`常時False・
`actual_entry_POST_allowed=False` / `actual_settlement_POST_allowed=False` ハードコード）。
テスト: `backend/app/tests/test_gmo_live_entry_final_preflight_no_post.py`。

## 1. repository gate（actual POST Stepでは stale tracking ref 不許可）

- [ ] branch = main
- [ ] HEAD == remote main（`git ls-remote` で確認）
- [ ] local origin/main tracking ref が追随済み（stale 不許可。no-POST Stepでは
      ls-remote 一致で継続可だが、actual POST Step では fresh clone/workspace で再確認必須）
- [ ] working tree clean（`git status --short` 空、`git diff --check` 通過）

## 2. evidence gate

- [ ] paper evidence: `PAPER_TRADE_EVIDENCE_CONFIRMED_SAFE_SUMMARY`
- [ ] anomaly evidence: `KILL_SWITCH_AND_SETTLEMENT_ANOMALY_TESTS_CONFIRMED`
      （synthetic-only では不可。read-only runtime safe confirmation 実行済み等の
      criteria を満たす場合のみ）

## 3. read-only runtime gate（current read-only Step または後続 fresh Step で確認）

- [ ] operator input block 5項目の current-turn 完全一致（過去Stepからの流用無効）
- [ ] credential presence safe boolean confirmed（値・長さ・hash・fingerprint・
      prefix/suffix は一切扱わない）
- [ ] runtime position: `NO_POSITION` / `count=0`
- [ ] active/pending orders: clear / `count=0`
- [ ] runtime read result: `READ_CONFIRMED_SAFE`（failed/timeout/unknown/rejected は停止）

## 4. no-POST entry foundation gate

- [ ] production real entry transport: fail-closed design present
      （`ProductionEntryTransportNotImplemented`。実HTTP write 経路なし）
- [ ] sealed credential real operation: design present, no value exposure
      （`SealedCredentialRealOperationDesignSkeleton`。activate は常に raise）
- [ ] runtime safe read real connection: design present, cannot execute in no-POST
      （`RuntimeSafeReadRealConnectionDesignSkeleton`。connect は常に raise）
- [ ] hard guard controlled supply: design present, no allow bridge,
      cannot resolve allow in no-POST（`HardGuardControlledSupplyDesignSkeleton`。
      resolve は常に raise・True を返す経路なし）
- [ ] entry permit: one-use / entry-only / no-banking（`gmo_live_entry_post_permit.py`）
- [ ] sanitized preview ready（`GmoEntryPostSanitizedPreview`。raw/ID/value なし）
- [ ] no_order / no-POST guard tests green

## 5. execution constraint gate（別Stepでのみ扱う）

- [ ] operator current-turn `ENTRY_BUY` / `ENTRY_SELL` / `HOLD`（未提供であること。
      本checklistおよび final preflight package は signal を保持できない）
- [ ] operator current-turn actual POST exact confirmation（未提供であること）
- [ ] max one POST / no retry / no repost / no second POST
- [ ] no settlement POST in entry step / no generic close
- [ ] result は sanitized category のみ（raw/ID/value/credential 非露出）

## 4b. production entry boundary gate（2026-07-07 追加・fail-closed 実装済み）

- [ ] `DisabledProductionEntryTransport` present（entry-only・activation 構築不能・
      send 常時 raise。`gmo_live_production_entry_boundary.py`）
- [ ] `SealedSecretBox` present（repr/str 非露出・unseal 常時 raise）
- [ ] runtime safe read connection adapter present（sanitized summary → snapshot
      純関数。unknown/stale/非0 は block）
- [ ] `HardGuardAllowControlledSupply` default-deny（truthy 構築は例外・allow bridge なし）
- [x] operator 書面 sign-off recorded（2026-07-07 記録済み:
      `docs/ACTUAL_ENTRY_SIGNOFF_RECORD_NO_POST.md`。sign-off は actual POST 許可では
      なく、actual Step では fresh final preflight + current-turn 入力が別途必須）

## 6. status 分類

`GmoEntryFinalPreflightStatus`:

- `BLOCKED_SAFE`: repo不安全 / exposure / retry・settlement・generic要求 / paper未確認
- `WAITING_FOR_NO_POST_ENTRY_FOUNDATION_COMPLETION`
- `WAITING_FOR_READ_ONLY_RUNTIME_OPERATOR_CONFIRMATION`
- `WAITING_FOR_SAFE_RUNTIME_RESULT`
- `WAITING_FOR_ANOMALY_EVIDENCE_CONFIRMATION`
- `READY_FOR_FINAL_PREFLIGHT_NO_POST`
- `READY_FOR_OPERATOR_ENTRY_CURRENT_TURN_CONFIRMATION`（record 互換のため残置。
  evaluator の終端は下記3statusに移行）
- `WAITING_FOR_PRODUCTION_ENTRY_CODE_BLOCKERS`（2026-07-07 追加）
- `WAITING_FOR_ACTUAL_ENTRY_SIGNOFF`（同）
- `READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST`（同・終端 ready）

いずれの status でも `actual_entry_POST_allowed=false` は不変。
`READY_FOR_ACTUAL_ENTRY_FINAL_PREFLIGHT_NO_POST` は「次の operator 入力
（entry signal / exact confirmation）を別Stepで求められる状態」を意味するだけで、
POST実行状態ではない。
