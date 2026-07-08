# Unattended Monitoring Guard & Paper Soak Readiness — no-POST実装記録

Step: `UNATTENDED_MONITORING_GUARD_AND_PAPER_SOAK_READINESS_NO_POST`
Date: 2026-07-08

## 1. 目的と対象範囲

unattended live に進む**前提条件**となる監視guard群と paper soak readiness を、
paper/fake/synthetic 環境のみで設計・実装・検証した。

対象: monitoring guard / unattended paper cycle state machine / cycle lock /
safe attempt ledger / fake notifier / paper soak readiness runner /
docs・runbook。

対象外(このStepで実施していないこと): actual POST、entry/settlement/close POST、
broker write、real HTTP、runtime private GET、credential・`.env` 読取、
daemon・cron・background worker・real scheduler・外部通知、live raw PnL adapter、
RiskPolicy変更、operator confirmation の削除・自動代替。

**unattended live remains unsupported / unattended full auto completed=false（不変）**。

## 2. no-POST安全境界

- 全moduleに broker / HTTP / credential / env / raw value surface が構造的に不存在
  （source-scanテストで固定: httpx / live_order_once / live_verification /
  os.environ / getenv / `/private/v1` 等の不在）
- guard入力は safe label / safe boolean のみ。raw price / spread / PnL /
  timestamp / ID の field 自体がない
- `GUARD_PASS` は actual permission ではない
  （`guard_pass_is_actual_permission=false` / `live_post_allowed=false` 固定・非truthy）
- paper completion は unattended live completed ではない（固定false field）

## 3. Guard一覧（`gmo_unattended_monitoring_guard.py`）

fail-closed(全UNKNOWNはhalt)・複数該当時は固定優先順位(下表の順)で decision:

| 優先 | guard | halt decision |
|---|---|---|
| 1 | kill switch(engaged / 状態不明) | GUARD_HALT_KILL_SWITCH |
| 2 | paper transport(real / unknown) | GUARD_HALT_REAL_TRANSPORT |
| 3 | state consistency | GUARD_HALT_STATE_INCONSISTENT |
| 4 | market unsafe/unknown | GUARD_HALT_MARKET_UNSAFE |
| 5 | ticker stale/unknown | GUARD_HALT_TICKER_STALE |
| 6 | spread out/unknown | GUARD_HALT_SPREAD_OUT_OF_LIMIT |
| 7 | position multiple/unknown・count mismatch/unknown | GUARD_HALT_POSITION_COUNT_MISMATCH |
| 8 | active/pending present/unknown | GUARD_HALT_ACTIVE_PENDING_PRESENT |
| 9 | max hold exceeded/unknown | GUARD_HALT_MAX_HOLD_EXCEEDED |
| 10 | max loss exceeded/unknown（safe categoryのみ・raw PnLなし） | GUARD_HALT_MAX_LOSS_EXCEEDED |
| 11 | consecutive failure | GUARD_HALT_FAILURE_LIMIT |
| 12 | unknown event | GUARD_HALT_UNKNOWN_EVENT |

## 4. State machine / lock / attempt ledger（`gmo_unattended_cycle_state_machine.py`）

- 状態: IDLE → SIGNAL_CANDIDATE → PREVIEW_READY → AWAITING_OPERATOR_CONFIRMATION →
  PAPER_ENTRY_REQUESTED → PAPER_ENTRY_ACCEPTED → PAPER_POSITION_OPEN →
  PAPER_SETTLEMENT_CANDIDATE → PAPER_SETTLEMENT_REQUESTED →
  PAPER_SETTLEMENT_ACCEPTED → PAPER_NO_POSITION_CONFIRMED → COMPLETED
  （+ HALTED は常に合法・terminal）
- illegal transition は safe halt(データを外に出さない)
- lock: `PAPER_SYNTHETIC_ONLY_NOT_BROKER_BOUND` scope固定。lockなし・scope不一致
  でのattemptは即halt
- attempt ledger: `PAPER_EVENT_*` safe categoryのみ受理(それ以外は例外)。
  entry / settlement 各**最大1回**、duplicateは記録のうえhalt。
  broker/order/position/transaction ID を保存する field は不存在

## 5. Fake notification（`gmo_unattended_fake_notifier.py`）

in-memory collector のみ(`external_send=false` 固定)。categoryは NOTIFY_* enum のみ。
FailingFakeUnattendedNotifier により「通知必須シナリオでの通知失敗 → safe halt」を検証。

## 6. Paper soak readiness runner（`gmo_unattended_paper_soak_runner.py`）

常駐なし・即時実行の synthetic scenario suite(21件)。guard → signal →
state machine + lock + ledger → fake transport(1回ずつ) → fake notifier の順で
1サイクルを回し、期待outcomeとの一致で判定する。

suite結果: **PAPER_SOAK_READINESS_PASSED（21/21 一致）**

| family | scenario | outcome |
|---|---|---|
| 正常系 | BUY/SELL full cycle | SCENARIO_COMPLETED_SAFE |
| 無発注 | HOLD / UNKNOWN | HOLD_NO_ORDER / SIGNAL_BLOCKED |
| guard halt | spread / ticker / market / active-pending / count mismatch / kill switch / max hold / max loss | SCENARIO_GUARD_HALTED_SAFE(attempt前) |
| no retry | entry rejected/unknown・settlement rejected/unknown | SCENARIO_HALTED_NO_RETRY_SAFE |
| duplicate | entry / settlement duplicate | SCENARIO_DUPLICATE_BLOCKED_SAFE |
| 構造 | illegal transition / notifier failure / real-like transport | 各blocked/halted/refused |

## 7. fail-closed policy

unknown は原則 halt。rejected / timeout / unknown に retry 分岐は存在しない。
guard halt は paper attempt の**前**に発生する。real-like transport は実行前拒否。

## 8. 運用手順

[UNATTENDED_MONITORING_RUNBOOK_NO_POST.md](UNATTENDED_MONITORING_RUNBOOK_NO_POST.md) 参照。
