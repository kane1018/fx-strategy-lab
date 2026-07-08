# Paper Auto Cycle Runner — no-POST実装記録（Step 6G Sprint Phase 3）

Step: `STEP_6G_PC_OX_Z_OPERATOR_GATED_CYCLE_CLOSEOUT_TO_SUPERVISED_AUTO_LIVE_PREVIEW_NO_POST_C` Phase 3
Date: 2026-07-08

## 1. 目的

自動判断ロジックの cycle 形状（signal → paper entry → one-position confirmation →
paper settlement → no-position confirmation）を、**実broker surfaceゼロ**で
検証可能にする。実POST / real HTTP / private GET / credential / `.env` /
sealed local value file 読取はいずれも構造的に不存在。

## 2. 実装

- `backend/app/services/gmo_paper_auto_cycle_runner.py`
  - `AutoPreviewSignal`（`AUTO_PREVIEW_SIGNAL_BUY / _SELL / _HOLD /
    _UNKNOWN_BLOCKED`）。**operator safe label（ENTRY_BUY等）ではない**。
    operator labelを渡すと例外で拒否（自動経路への流用を構造的に禁止）
  - `run_gmo_paper_auto_cycle_once`: fake/paper transport のみ受理
    （`is_real_transport` が true または未マークの transport は実行前拒否）。
    paper entry 最大1回 + paper settlement 最大1回。非accepted結果は即
    hard stop（retry/repost/second分岐なし）。HOLDは発注ゼロ、UNKNOWNはblock、
    scenario gate（market/ticker/spread/flat/active-pending の safe boolean）
    不足はentry前block
  - `PaperAutoCycleScenario` / `run_paper_auto_cycle_scenario`: 決定論的
    シナリオ実行（synthetic fixture）
  - 結果は safe label / safe count / 固定false flag のみ
    （`actual_entry_POST_allowed=false` / `actual_settlement_POST_allowed=false` /
    `real_post_count=0` / `__bool__` False）
- `backend/app/tests/test_gmo_paper_auto_cycle_runner_no_post.py`
  - buy/sell完走・hold無発注・unknown block・gate毎block・非accepted停止・
    real-like transport拒否・operator label拒否・決定論性・source isolation

## 3. 禁止事項の固定

live POST / real HTTP / private GET / credential / broker状態変更 /
operator confirmation banking は、fieldの不存在・transport拒否・
source-scanテストにより構造的に不可。
