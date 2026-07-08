# Supervised Auto Live Preview — no-POST実装記録（Step 6G Sprint Phase 4）

Step: `STEP_6G_PC_OX_Z_OPERATOR_GATED_CYCLE_CLOSEOUT_TO_SUPERVISED_AUTO_LIVE_PREVIEW_NO_POST_C` Phase 4
Date: 2026-07-08

## 1. 目的

自動判断ロジックが「何を提案するか」「live POSTの前に何がまだ必要か」を、
live POST 直前の形まで **preview のみ**で提示できる状態を作る。
live POST / broker write / real HTTP / credential / private GET /
sealed value file 読取は行わず、preview は permission ではない。

## 2. 実装

- `backend/app/services/gmo_supervised_auto_live_preview.py`
  - `derive_auto_preview_signal`: safe label のみから機械導出
    （UPTREND→`AUTO_PREVIEW_SIGNAL_BUY` / DOWNTREND→`_SELL` / FLAT→`_HOLD` /
    それ以外・gate不成立・建玉あり→`_UNKNOWN_BLOCKED`。fail-closed）
  - `build_gmo_supervised_auto_live_preview`: preview package を構築
    - `auto_preview_signal_is_operator_signal=false` 固定
      （AUTO_PREVIEW_SIGNAL_* は operator_signal_type ではない）
    - BUY/SELL preview は `required_future_gates`（fresh repo / fresh runtime
      read / operator current-turn confirmation not banked / sealed value /
      final preflight / sanitized preview / reviewed sender injection /
      one-use permit+activation / default-deny hard guard）と
      `required_future_operator_input_names`（**入力名のみ・値は絶対に持たない**）
      を提示
    - HOLD / BLOCKED preview は発注提案なし（gates空）
    - `why_not_permission` 固定文言で「previewは許可ではない」ことを package
      自身が回答
    - `actual_entry_POST_allowed=false` / `actual_settlement_POST_allowed=false` /
      `operator_confirmation_generated=false` / `hard_guard_allow_resolved=false` /
      `__bool__` False
- `backend/app/tests/test_gmo_supervised_auto_live_preview_no_post.py`
  - 導出mapping・BUY/SELL≠operator label・HOLD無発注・default block・
    建玉ありでentry preview不成立・confirmation値fieldの不存在・
    permission固定false・source isolation

## 3. 4つの問いへの回答（package仕様）

1. 自動化は何を提案するか → `proposed_action_safe_label`
2. live POST前に必要なgateは → `required_future_gates`
3. 必要なoperator入力は → `required_future_operator_input_names`（名前のみ）
4. なぜpreviewは許可でないか → `why_not_permission`

## 4. 次接続

preview を operator が採用する場合も、従来どおり別Stepの fresh gate 一式と
operator current-turn confirmation（完全一致・banking不可）が必須。
unattended live は
[UNATTENDED_GAP_ASSESSMENT_NO_POST.md](UNATTENDED_GAP_ASSESSMENT_NO_POST.md)
のとおり当面 unsupported。
