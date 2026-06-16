# FX レポート標準化プラン（次フェーズ設計）

単純テクニカル研究フェーズはクローズ済み（[fx_research_m5_summary.md](fx_research_m5_summary.md)）。
次フェーズは新戦略探索ではなく、**検証基盤とレポート出力の標準化**。本書は設計・方針のみで、
この段階では writer 共通化のコード実装・UI実装・E2E導入は行わない。

すべて read-only paper の検証基盤の話であり、実注文・Private API・APIキーは扱わない。

## 1. 目的

- 既存の各15窓ランナーがそれぞれ独自に書いている `manifest.json` / `warnings.json` /
  `summary.md` / `metrics_*.csv|json` を、共通スキーマに揃える。
- run 同士・戦略同士を機械的に比較でき、将来のレポート一覧UI / run詳細UIにそのまま載せられる
  データ構造にする。
- read-only / no real order / no private api の安全状態を、全 run で同一フォーマットで表示する。

## 2. analysis_exports の理想構成

`analysis_exports/` は gitignore（生成物）。1 run = 1 ディレクトリ。

```text
analysis_exports/<run_id>/
  manifest.json                 # run のメタデータ + 固定条件 + 安全メタデータ
  warnings.json                 # 安全フラグ + データ欠損などの注意 + 指標定義
  summary.md                    # 人間が読む要約（表中心）
  metrics_<scope>_summary.json  # 機械可読の集計（15窓全体）
  metrics_by_window.csv
  metrics_by_symbol.csv
  metrics_by_exit_reason.csv
  metrics_by_date.csv
  metrics_by_market_state.csv   # 該当する診断のみ
  <strategy>_final_decision.md  # 採用/研究用/撤退 の判定と根拠
```

- `run_id` 形式: `YYYYMMDD_HHMMSS_gmo_public_paper_<kind>`（既存 `fx_eval_common.run_id` 準拠）。
- ファイル名は固定。存在しない scope のファイルは出さない（無理に空ファイルを作らない）。

## 3. manifest.json に入れるべき項目

`fx_eval_common.fixed_config()` + `safety_metadata()` を土台に、最低限:

- `run_id` / `created_at` / `kind` / `strategy`
- 固定条件: `timeframe` / `cost_scenario` / `spread_pips` / `slippage_pips` /
  `stop_loss_pips` / `take_profit_pips` / `exit_policy` / `symbols` / `continuous_replay`
- 戦略パラメータ（該当時）: 例 `bollinger_period` / `swing_lookback` など
- `windows`: 各 window の label / group(prior10|oos5) / dates
- 安全メタデータ: `real_order=false` / `private_api_used=false` / `api_key_used=false` /
  `no_order_execution=true` / `gmo_readonly=true` / `gmo_order_enabled=false`

## 4. warnings.json に入れるべき安全項目

- 上記 `safety_metadata()` を必ず含める（UI / E2E の安全表示の単一ソース）。
- `data_source`（"GMO Public API klines (BID), read-only"）/ `mode`（"read-only paper"）
- `no_trading`（診断系）/ `no_sklearn`（該当時）
- 指標定義（DE / ATR相当 / reversals / cost_ratio など、再現に必要な式）
- ラベル/閾値の決め方（例: DE三分位は prior10 で決め oos5 へ固定適用）
- `fetch_warnings`: データ欠損（祝日でklines無し等）。例: 2026-01-01 / 2025-12-25 は9営業日

## 5. summary.md の構成（節の順序を固定）

1. タイトル + 固定条件 + 安全注記（実注文なし等）
2. window別 結果表
3. 15窓全体集計
4. prior10 vs oos5
5. 戦略間比較（該当時、参照 run を明記）
6. symbol別
7. exit_reason別
8. market-state別（該当時）

## 6. metrics csv/json の命名規則

- CSV: `metrics_by_<scope>.csv`（scope = window / symbol / exit_reason / date / market_state）。
- 集計 JSON: `metrics_<kind>_summary.json`。
- CSV 共通列順: キー列（window/symbol/...） → 統計列（`fx_eval_common` の `_STAT_FIELDS` 準拠：
  completed_trades / win_rate / total_pnl / expectancy / profit_factor / max_drawdown /
  max_loss / max_consecutive_losses / sl_count / sl_ratio / opp_count / opp_total_pnl /
  forced_close_count / forced_close_ratio、TP拡張時は tp_count / tp_total_pnl）。
- 集計 JSON 共通キー: median_expectancy / median_pf / positive_windows / negative_windows /
  edge_windows / windows_ge30_trades / total_pnl / max_drawdown_max / group_prior10 /
  group_oos5 / symbol_pnl / verdict。

## 7. ChatGPT相談用レポートの標準フォーマット

各 run 報告で使ってきた貼り付け用ブロックを定型化（run情報 / 検証目的 / 固定条件 /
window別 / 全体集計 / prior10 vs oos5 / 戦略比較 / symbol別 / exit_reason別 /
market-state別 / 重要な発見 / warnings(JSON) / 暫定結論 / 次の仮説 / 実装結果 /
安全性確認 / 相談したいこと）。将来は summary.json から自動生成できる形にする。

## 8. 将来UIで表示すべき項目

- レポート一覧: run_id / kind / strategy / timeframe / verdict / median_expectancy /
  total_pnl / created_at / 安全バッジ（read-only / no real order / no private api）。
- run詳細: manifest / warnings(安全フラグを目立たせる) / summary.md / 各 metrics テーブル /
  CSV・JSON・Markdown のダウンロード導線。
- 危険操作（実注文・Private API）は **存在しない**ことを明示。トグルや実行ボタンは置かない。

## 9. 次フェーズ優先順位

1. analysis_exports 出力構造の標準化（本書のスキーマへ既存ランナーを寄せる）
2. manifest / warnings / summary / metrics writer の共通化（`fx_eval_common` 拡張）
3. report schema の固定（summary.json のキーを契約として固定）
4. 安全表示（safety_metadata）の単一ソース化
5. レポート一覧UI / run詳細UI に備えたデータ構造整理
6. E2E導入候補フローの docs 化（§11）

まだ行わないこと: E2Eツール導入 / Playwright・Cypress 追加 / UI実装 / 実注文 / Private API接続 /
依存パッケージ追加。

## 10. E2E導入タイミング

戦略研究フェーズ終了直後の現時点では **E2Eは導入しない**（package追加もしない）。
導入は、以下がすべて揃ってから:

- レポート一覧画面
- run_id 詳細画面
- summary / metrics / warnings 表示
- read-only / no real order / no private api の安全表示
- CSV / JSON / Markdown の確認またはダウンロード導線
- 危険操作が存在しない、または明示的に無効化されていること

## 11. 最初のE2E対象フロー（将来）

1. レポート一覧を開く
2. run_id を選ぶ
3. summary / metrics / warnings を確認する
4. safety flags を確認する
5. 実注文や Private API 操作が存在しないことを確認する

## 12. E2Eで確認すべき安全項目

- `real_order = false` / `private_api_used = false` / `api_key_used = false`
- `gmo_readonly = true` / `gmo_order_enabled = false` / `no_order_execution = true`
- 画面・API応答に APIキー / secret / `.env` 値が出ないこと
- 実注文ボタン・Private API 実行導線が存在しない、または無効であること
