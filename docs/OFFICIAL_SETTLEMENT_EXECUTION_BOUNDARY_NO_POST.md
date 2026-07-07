# Official Settlement Execution Boundary — no-POST実装記録（Step 6G）

Step: `STEP_6G_PC_OX_X_OFFICIAL_SETTLEMENT_EXECUTION_BOUNDARY_SELF_DRIVE_NO_POST_C`
Date: `2026-07-08`

## 1. 本Stepの目的

official settlement preflight READY 後、actual settlement gate が
**コード変更なし**で進める状態を作る。self-drive監査の結果、
dedicated route / side provenance / sealed size source / hard guard /
sanitized preview は既存実装で READY、一方 settlement 専用の
sender boundary / one-use permit / activation / 単一 call site が未実装
（entry permit は SETTLEMENT scope を構造的に拒否するため流用不可）だったため、
entry 側と同型の boundary を no-POST で追加した。

**本Stepおよび本モジュール群は settlement POST / closeOrder POST / entry POST を
一切実行せず、実行許可も与えない**（`actual_settlement_POST_allowed=false` 維持・
activation/permit/result はすべて `__bool__` 常時 False）。

## 2. 実施内容（no-POST）

- `backend/app/services/gmo_live_official_settlement_execution_boundary.py` を追加
  - settlement専用 current-turn operator input と必須完全一致文字列:
    - `CONFIRM_ONE_SETTLEMENT_POST_MAX_NO_RETRY_NO_REPOST_NO_ENTRY`
    - `OPERATOR_READY_FOR_ONE_SETTLEMENT_POST_MAX_NO_RETRY_NO_REPOST`
    - `OPERATOR_ACKNOWLEDGES_ACTUAL_BROKER_WRITE_RISK`
    - entry用confirmationの流用はテストで拒否を固定
  - settlement側は operator field ではなく、prior entry signal からの機械写像のみ
    （ENTRY_BUY -> SETTLEMENT_SELL）。HOLD/unknown は fail-closed
  - one-use settlement permit（SETTLEMENT_ONLY scope・entry/generic/cancel/change
    scope拒否・single-use・hard guard非解決）
  - one-use activation（12 gate すべて充足時のみ granted・非truthy・
    `grants_hard_guard_allow` は granted 由来のみ）
  - `send_official_settlement_post_once`: 単一レビュー済みcall site。
    OFFICIAL_SETTLEMENT plan 限定（entry/generic plan は送信前block）、
    共有hard guard通過、最大1回送信、いかなる結果でも再送分岐なし
  - Fake / Refusing sender（default状態では実送信不能を証明）
- `backend/app/services/gmo_live_official_settlement_sender.py` を追加
  - `GmoOfficialSettlementOneShotHttpSender`（one-shot・one-attempt・
    sealed credential内部unseal・sanitized outcome変換・inert timestamp default）
  - 実HTTP client / 実credential / 実timestamp factory は actual settlement
    execution step でのみ注入
- tests 2ファイル追加（operator input完全一致 / permit fail-closed /
  activation gate毎denial / 単一call site one-shot / entry plan拒否 /
  非accepted結果でも再送なし / sender mapping / module isolation source-scan）

## 3. 安全制約（本Step）

- actual POST / settlement POST / closeOrder POST / entry POST: `false`
- broker write / real HTTP write: `false`
- generic close / generic opposite order as close / live_order_once流用: なし
- retry / repost / second POST: 構造的に不可
- raw request / response / ID / 数量 / 価格 / 損益 / credential / signature /
  header / raw numeric size: 非露出
- runtime read-only確認: 1回のみ実施（ONE_POSITION_OPEN / COUNT_ONE /
  NO_ACTIVE_PENDING_ORDERS / COUNT_ZERO）。actual gate では fresh 再確認必須
- `actual_settlement_POST_allowed`: `false`（不変）

## 4. 次接続（別Step: actual settlement gate）

次の actual settlement gate では以下が **fresh に** 必須:

1. fresh repository check / fresh read-only runtime read
   （ONE_POSITION_OPEN / COUNT_ONE 再確認・market/ticker/spread safe labels）
2. operator current-turn settlement 専用入力（上記3文字列と完全一致・banking不可）
3. sealed settlement size source の fresh 確認（値非露出）
4. 実 sender の reviewed injection（実HTTP client / sealed credential /
   実timestamp factory・1 call siteのみ）
5. hard guard（default-deny）通過・one-use permit / activation
6. 最大1回のPOST・結果は sanitized category のみ・POST後は停止
