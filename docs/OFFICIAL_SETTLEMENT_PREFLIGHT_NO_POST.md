# Official Settlement Preflight — no-POST実装記録（Step 6G）

Step: `STEP_6G_PC_OX_W_OFFICIAL_SETTLEMENT_PREFLIGHT_NO_POST_C`
Date: `2026-07-08`

## 1. 本Stepの目的

accepted entry POST 後の `ONE_POSITION_OPEN / COUNT_ONE` 確認を受け、公式
settlement route の no-POST preflight を実装する。**本Stepおよび本モジュールは
settlement POST / close POST / entry POST を一切実行せず、実行許可も与えない**
（`actual_settlement_POST_allowed=false` ハードコード・`__bool__` 常時 False）。

## 2. 実施内容（no-POST）

- `backend/app/services/gmo_live_official_settlement_preflight.py` を追加
  - settlement side provenance: 直前 entry signal safe label からの機械写像のみ
    （`ENTRY_BUY -> SETTLEMENT_SELL` / `ENTRY_SELL -> SETTLEMENT_BUY`。
    HOLD/unknown は derivable でなく fail-closed。AIは方向を判断しない）
  - `SealedOfficialSettlementValueSource`: operator local file
    （`.approved_entry_internal_value.local.json`・gitignored）由来の sealed
    settlement size source。値の返却・表示・ログ経路なし、エラーは非echo、
    唯一の内部consumerは専用 settlement plan builder への直接受け渡しのみ
  - `review_official_settlement_route()`: 専用 `POST /private/v1/closeOrder`
    size-based route の構造確認（generic opposite order 経路なし）
  - `build_gmo_official_settlement_preflight_package()`: default-deny の
    preflight package（route / side provenance / size source / one-position /
    active-pending clear / violations を safe label で分類）
  - `GmoOfficialSettlementSanitizedPreview`: safe labelのみの preview
    （raw size / price / PnL / ID / credential のfieldは構造的に不存在）
  - position-specific settlement は
    `POSITION_SPECIFIC_PATH_BLOCKED_SAFE_IDENTIFIER_HANDLING_NOT_READY` 固定
- `backend/app/tests/test_gmo_live_official_settlement_preflight_no_post.py` を追加
  - side機械写像 / sealed非露出 / loader fail-closed / settlement-only plan検証 /
    entry plan拒否 / package default-deny / preview safe-label-only /
    module source isolation（httpx・live_order_once・os.environ等の不在）

## 3. 安全制約（本Step）

- actual POST / entry POST / settlement POST / close POST: `false`
- generic close / generic opposite order as close: `false`
- retry / repost / second POST: `false`
- raw request / raw response / broker response本文: 非露出
- ID / 数量 / 価格 / 損益 / credential / signature / header: 非露出
- `actual_settlement_POST_allowed`: `false`（不変）
- current-turn settlement confirmation の banking: 構造的に不可（field不存在）

## 4. 次接続（別Step: actual settlement gate）

次の actual settlement gate では以下が **fresh に** 必須:

1. fresh repository check / fresh read-only runtime read
   （`ONE_POSITION_OPEN / COUNT_ONE` 再確認）
2. operator current-turn settlement 専用入力（entry用confirmationの流用不可・
   完全一致必須）
3. settlement 専用 one-shot sender の reviewed injection（1 call siteのみ・
   最大1回・retry/repost/second POST禁止）
4. hard guard（default-deny）通過と one-use permit / activation
5. 結果は sanitized category のみ報告
