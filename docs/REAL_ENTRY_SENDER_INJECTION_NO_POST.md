# Real Entry Sender Injection — no-POST実装記録（Step 6G）

Step: `STEP_6G_PC_OX_R_REAL_ENTRY_SENDER_INJECTION_IMPLEMENTATION_NO_POST_C`
Date: `2026-07-07`

## 1. 本Stepの目的

直前 Step の `actual sender not injected` ブロッカーを解消するため、actual entry POST の
実送信 sender 実装を no-POST で追加し、次の actual entry gate が
**コード変更なし**で `fresh current-turn` + `fresh runtime` + `fresh final preflight` で進められる状態を作る。

## 2. 実施内容（no-POST）

- `backend/app/services/gmo_live_actual_entry_sender.py` を追加
  - `ActualEntryOneShotSender` 向けの concrete sender を実装。
  - Protocol:
    - `ActualEntrySenderHttpClient`
    - `SealedCredentialForActualEntry`
  - `GmoActualEntryOneShotHttpSender`（one-shot, one-attempt）を追加。
  - raw request/response/ID/credential/signature/header を境界外に出さない構成。
  - `send_entry_once_sanitized` は例外を safe category に集約して返却。
- `backend/app/tests/test_gmo_live_actual_entry_sender_no_post.py` を追加
  - response/status の safe mapping
  - exception mapping
  - no retry / no second send path
  - sender source-scan（`live_order_once` / `closeOrder` / `settlePosition` 不在）

## 3. 安全制約（本Step）

- actual POST / entry POST / settlement POST / close POST: `false`
- retry / repost / second POST: `false`
- runtime private GET: `false`
- credential value read / .env read: `false`
- raw request / raw response / broker response本文: `false`
- ID / price / size / PnL / credential / signature / header の外部露出: `false`
- `actual_entry_POST_allowed` 維持: `false`

## 4. 実装結果と次接続

`gmo_live_actual_entry_execution_boundary.py` は `ActualEntryOneShotSender` を
injection point として保持しており、実送信 sender は上記の concrete sender を
構築して inject 可能。
`GmoActualEntryOneShotHttpSender` は this Step では fake HTTP クライアントでのみテストされるため、
実ネットワーク送信を実行しない。

次 actual entry gate の到達条件（別Step）:

- fresh repository / fresh runtime safe read / fresh final preflight
- operator current-turn の 5/7項目完全一致（過去値/推定/補完不可）
- hard guard explicit allow derivation
- one-shot permit + one-use activation + sender 注入
- no retry/repost/second POST

本Stepの safe result は `RESULT_BLOCKED_BEFORE_POST_SANITIZED` ではなく
`CASE A` へ進める（no-POST での実装完了、次 step での実行可能準備完了）.
