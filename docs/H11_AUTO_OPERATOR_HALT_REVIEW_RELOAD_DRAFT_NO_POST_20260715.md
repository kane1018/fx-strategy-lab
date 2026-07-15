# H-11 Auto Operator HALT Review / Reload Draft（docs-only / no-POST）

Date: 2026-07-15

Status: `DRAFT_GENERIC_PHASE_B_V4_HAS_SEPARATE_IMPLEMENTED_NO_POST_RELOAD`

> 2026-07-15 update: 本書のgeneric Phase B案は維持する。選定済みGMO relaxed v4だけは、
> `H11_V4_GMO_OPERATOR_RUNBOOK_NO_POST_20260715.md`によりexact phrase＋fresh fake flat、
> history保持、no automatic resumeの限定reloadを実装済みである。actual reloadではない。

## 1. Purpose

`HALTED_OPERATOR_REVIEW_REQUIRED`を自動復帰させず、原因・永続状態・再発防止をoperatorが確認した後に
だけ、新しいrun generationを開始する手順を定義する。

本書はPhase B fake-only用の草案であり、HALT解除API、actual activation、broker access、credential、
POSTを実装・許可しない。

## 2. Non-negotiable rules

```text
automatic_restart_from_halt=false
mutate_halted_row=false
delete_halted_database=false
reset_attempt_count=false
reuse_old_checkpoint=false
retry_unknown_entry_or_exit=false
generic_allow_bridge=false
actual_post=false
```

HALT済みSQLiteは監査記録として不変保持する。同じDB内のHALT rowをUPDATE / DELETEして再利用しない。
再開が承認された場合も、新しい空のstate directoryと新しいgeneration labelを使う。

## 3. HALT classification

### Safety-critical

- entry / exit result unknown
- partial-fill protection mismatch
- missing / excess server-side protection
- local / broker state mismatch
- external or manual position conflict
- active order conflict
- duplicate process / lock anomaly
- journal verification failure
- credential / permission / notification anomaly

将来actualに関係する上記原因は、broker read-only reconciliationと独立safety reviewなしにreloadしない。

### Phase B local-only

- synthetic notifier failure
- stale local formal signal
- local fixture schema error
- wall-clock observation gap
- test process interruption

local-only原因でも、古いDBやcheckpointを直接再利用しない。

## 4. Safe review sheet

operatorへ提示してよいのは次だけ。

```text
generation_label
policy_version
selected_horizon
safe_state_label
halt_reason_code
entry_attempt_count
exit_attempt_count
journal_valid
last_updated_at_utc
heartbeat_age_seconds
actual_post_count
broker_write_performed
network_access_performed
credential_read_performed
```

intent / order / execution / position ID、raw response、credential、signature、価格、数量は表示しない。

## 5. Phase B fake-only reload proposal

以下の全条件を満たした後だけ、operatorが別Stepで新generation作成を承認する。

1. 旧processが終了している。
2. 旧checkpointとSQLiteのsafe aggregateをread-onlyで確認した。
3. journal verificationが成功した。
4. HALT reasonがlocal synthetic原因として説明できる。
5. unknown actual state、broker state、credential問題ではない。
6. policy version、config hash、selected horizonを変更しない。
7. 新しいstate directory / checkpoint / lock pathを割り当てる。
8. 新generationで100-cycle synthetic fault soakが成功する。
9. operatorが旧generationを再利用しないことを明示承認する。

この手順はpaper/fake-onlyの継続を許すだけで、actual transportやliveを許可しない。

## 6. Future actual reload requirements

actualでHALTした場合は、本草案だけで再開しない。少なくとも次を追加する。

- fresh broker read-only position / active-order reconciliation
- pending / partial / protected sizeの公式状態確認
- unknown resultに対するno-resend確認
- loss budget / daily attempt / incident state確認
- notification / dead-man / execution host / clock確認
- dedicated account ownership確認
- independent safety reviewer clear
- operator current-turn resume declaration
- separate actual activation authorization

重大インシデント後のresumeは汎用booleanから生成せず、その時点のfresh evidenceで判断する。

## 7. Generic Phase Bで未実装

```text
reload_command=false
halt_clear_endpoint=false
database_reset=false
checkpoint_resume=false
actual_reconciliation=false
broker_read=false
credential_read=false
actual_post=false
```

generic Phase B reloadは別授権対象のままである。GMO relaxed v4限定実装はHALT rowを削除・resetせず、
監査可能な`OPERATOR_RELOAD_CLEARED` terminal stateへ遷移し、同じ操作ではresumeしない。
