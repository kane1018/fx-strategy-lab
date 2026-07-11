# H-11 v3 Observed Unattended Live Policy（activation前・no-POST）

Date: 2026-07-11

Policy ID: `H11_V3_OBSERVED_UNATTENDED_LIVE_POLICY`

Status: **ACTIVE_FOR_NO_POST_IMPLEMENTATION_ONLY**

## 1. Operator採用方針

> 収益性の検証期間は短縮し、極小額liveで並行収集する。一方、二重注文防止、結果不明時停止、
> server-side損失限定、reconciliation、credential保護はlive開始前条件として省略しない。
> operatorの目視は安全性を補助するが、自動執行の成立条件にはしない。

本方針は従来のStage 1→2→3の実時間待機をactual liveの事前条件から外す。ただし収益性を
証明済みにせず、liveをengineering burn-inと継続評価の場として扱う。

## 2. 新Stage

### V3-BUILD — no-POST safety implementation

- v3 spec freeze
- IFDOCO pure builder
- persistent lock / intent-first safe state
- fake lifecycle / fault injection
- credential/env/API/network/POSTなし

### V3-BURN-IN — observed unattended live（将来・別activation）

- signalからentry・broker-side OCO・reconcile・settlementまで自動
- per-trade confirmationなし
- operatorは目視・通知確認・kill・停止後reloadを担当
- operator不在を理由に個々のexecutionを待たない
- 最大1pair、1position、1entry/day、凍結10,000 units
- `OPERATOR_SELECTED_UNPROVEN` / `performance_proof_status=false`を維持

### V3-REVIEW — 継続判断

- safe aggregateで収益性・約定品質・規律・停止・reconcileを採点
- 良績で増額しない
- spec変更はv4・新config hash
- 予算または停止基準到達後は自動再開しない

## 3. 旧Stage条件の扱い

| 旧条件 | 新しい扱い |
|---|---|
| Stage 1 2週間＋20 paper trades | actual live開始の前提から外し、並行scorekeeperへ移す |
| Stage 2 4週間＋10 live trades | 自動化解除の前提から外し、V3-BURN-IN review指標へ移す |
| E1 14日gate | actual live開始の前提から外す。E1 status自体は変更しない |
| per-trade current-turn confirmation | V3-BURN-INでは除去。ただしactual activation文書とAGENTS.md改定前は除去未発効 |
| profitability gate | 事前permissionではなく継続・停止判断のscorekeeper |

```text
E1_status=E1_IMPLEMENTED_NOT_GATE_PASSED
E1_gate_passed=false
performance_proof_status=false
```

## 4. Live前のhard gate

```text
v3_spec_frozen
AND official_api_capability_review_complete
AND broker_native_pending_expiry_confirmed
AND server_side_oco_reconcile_design_complete
AND persistent_cycle_lock_tested
AND intent_first_state_tested
AND duplicate_attempt_blocked
AND unknown_result_halts
AND boot_reconcile_first
AND budget_and_stop_enforced
AND kill_and_dead_man_tested
AND notification_path_tested
AND sealed_credential_boundary_reviewed
AND complete_diff_review_clear
AND focused_and_related_tests_pass
AND separate_actual_activation_authorized
```

1条件でもfalse/unknownならactual transportをbindせず、POST permissionを作らない。

## 5. POST契約（将来のactivationでのみ発効）

- IFDOCO protected entry: 1 intentにつき最大1 attempt
- timeout / network / client / server / unknownはattempt消費、再送なし
- broker-side OCO決済は追加POSTなし
- 24h timeout settlementは別intent・official dedicated settlement route・最大1 attempt
- generic opposite entry、generic close、retry、repost、second attemptは禁止
- pending entryのcancelはv3非搭載。broker-native expiryがなければactivation拒否
- unknownまたはreconcile不一致後は全新規entry停止

## 6. 現在の授権境界

本方針のACTIVEはno-POST実装だけに効力を持つ。actual liveをまだ許可しない。

```text
policy_revision_authorized=true
h11_v3_spec_authorized=true
limited_no_post_implementation_authorized=true
actual_transport_binding_authorized=false
credential_env_read_authorized=false
private_api_authorized=false
broker_read_authorized=false
actual_post_authorized=false
resident_process_authorized=false
cron_authorized=false
commit_authorized=false
push_authorized=false
```

actual liveへ進むには、V3-BUILDの差分と検証結果をoperatorへ提示し、
`H11_V3_ACTUAL_ACTIVATION_STEP`を別途明示授権する。
