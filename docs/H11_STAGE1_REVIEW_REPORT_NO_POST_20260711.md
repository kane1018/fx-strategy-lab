# H-11 v2/v3 コードレビュー — 月次損失記録の消失バグ（no-POST）

Date: 2026-07-11

Status: **FOUND_AND_FIXED**

## 経緯

`min_open_order_size`の誤記録（別件、修正済み）を契機に、operatorから「他にも同種の誤りがないか」
との指摘があり、capability contract全項目の棚卸しと、未精読だったv3モジュール
（`h11_v3_ifdoco_profile.py`後半・`h11_v3_runtime_safety.py`・`h11_v3_observed_live_state.py`・
`h11_v3_fault_soak.py`）を通読した。

## 発見: monthly_loss_jpyが暦月切り替わりで無条件リセットされる

対象:
- `backend/app/services/h11_stage1_paper_wiring.py`（v2 Stage 1・**現在稼働中**）
- `backend/app/services/h11_v3_runtime_safety.py`（v3・未activation）

```python
# 修正前
if self._current_month != month:
    self._current_month = month
    self._monthly_loss_jpy = 0   # stop_stateを見ずに無条件リセット
```

`STOPPED_MONTHLY_BUDGET`で停止中に暦月が変わると、`stop_state`自体は正しく維持され
新規entryは引き続きブロックされる（**安全動作への影響はない**）が、停止を引き起こした
実際の損失額が黙って0にリセットされる。ACTIVE policyが要求する
「post-mortem必須→冷却期間14日→review window承認」という手順のうち、
**post-mortemの材料（損失額）が月をまたいだ時点で消える**という監査証跡の欠落があった。

月末近くで停止し、post-mortemの実施が翌月にずれ込むケースで実際に起こり得る
（v2 Stage 1は現在稼働中のため、理論上のリスクではなかった）。

## 修正

`stop_state`がACTIVEの時だけ月次リセットする形に変更（daily側の既存ロジックと同じ考え方）。

```python
if self._current_month != month:
    self._current_month = month
    if self.stop_state is H11Stage1StopState.ACTIVE:
        self._monthly_loss_jpy = 0
```

## 追加した回帰テスト

- `test_h11_stage1_paper_wiring_no_post.py::test_monthly_loss_figure_survives_month_rollover_while_stopped`
- `test_h11_v3_runtime_safety_no_post.py::test_risk_stops_on_monthly_budget_and_loss_figure_survives_rollover`
  （v3側は月次停止そのものの専用テストが存在しなかったため、停止発火〜rollover〜reloadまでの
  一連の流れを新規カバー）

## その他の確認（棚卸し・追加修正なし）

- `H11_V3_CAPABILITY_CONTRACT`全項目を検証済み事実と突合 — `min_open_order_size`以外は全て正しい
  （symbol・size_step・tick_size・public_spec_review_date）
- `h11_v3_ifdoco_profile.py`の価格算出ロジック（entry/SL/TP丸め方向）— BUY/SELL双方向で
  一貫して保守的な丸め、tick_size/symbol/size不一致はfail-closedで拒否。バグなし
- `h11_v3_observed_live_state.py`（state machine・process lock） — 遷移表・fcntl排他ロック・
  crash-safe永続化とも健全。バグなし
- `h11_v3_fault_soak.py` — シナリオ網羅性・soak駆動ロジックとも健全。バグなし
## 追加修正: 連敗停止と月次停止の同時発火時の優先順位をv2/v3で統一（2026-07-11）

上記レビューで副次的に見つけた不整合（v2の`record_paper_trade_outcome_jpy`は
consecutive判定とmonthly判定が独立した`if`文で両方成立時はmonthlyが上書きしていたが、
v3の`record_h11_v3_closed_result`は`if/elif`連鎖でconsecutive優先・排他）について、
operatorの指示によりv2側をv3と同じ`elif`連鎖（consecutive > monthly > daily）に統一した。

安全動作（新規entryのブロック）への影響はどちらの実装でも同一だったが、統一により
「どの条件が停止理由として記録されるか」が両バージョンで完全に決定論的・一致する形になった。

修正に伴い、偶然にconsecutive条件とmonthly条件を同時に満たしていた既存テスト2件
（`test_monthly_budget_stop_fires_and_same_month_reload_refused`・
`test_monthly_loss_figure_survives_month_rollover_while_stopped`）のデータパターンを、
月次条件のみを単独で発火させる形（4損失+1勝ち×2+2損失、5,000円/日）に再設計し、
両条件が同時発火した場合にconsecutiveが優先されることを検証する専用テスト
`test_simultaneous_consecutive_and_monthly_trigger_prefers_consecutive`を新規追加した。

## 検証

```text
backend_full_tests=7537_passed（min_open_order_size修正前7534
  → monthly_loss_jpy保持修正+回帰2件で7536 → 優先順位統一+新規テスト1件で7537）
wall_clock_24h_soak=継続中・生存確認済み
```
