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
   — **着手済み**: `fx_eval_common` に共通 writer（`ensure_output_dir` / `write_json` /
   `write_manifest` / `write_warnings` / `write_csv` / `write_metrics_csv` /
   `write_summary_markdown` / `write_markdown`）を追加。移行済み: `rsi_final_15window.py`（1本目）、
   `breakout_15window.py`（2本目）、`bollinger_15window.py`（3本目）、
   `market_structure_15window.py`（4本目）、`rsi_m15_15window.py`（5本目）、
   `rsi_m15_scaled_15window.py`（6本目）。TP拡張CSV＋market-state別CSVは
   `write_metrics_csv(..., stat_fields=BK_STAT_FIELDS)`、final_decision は `write_markdown`。
   scaled移行に伴い rsi_m15 の `_write_csv` 委譲wrapperは撤去済み（どのランナーからも未参照）。
   いずれも出力内容は不変・mechanism のみ共通化。さらに `regime_predictability_diagnostics.py`
   （7本目）も移行完了：フラットdict型CSV（by_rule / by_window / by_symbol / confusion_matrix）は
   `write_csv(path, rows, fieldnames)` で対応（`write_csv` 本体は無改修で適用可）。
   **主要ランナー全7本の出力writer標準化が完了**（stats入れ子型=write_metrics_csv、
   フラットdict型=write_csv の両系統が実戦投入済み）。`_summarize_bk` の共通化は別タスクで判断。
3. report schema の固定（summary.json のキーを契約として固定）
   — **着手済み**: `fx_eval_common` に `STRATEGY_SUMMARY_REQUIRED_KEYS`（window_count /
   median_expectancy / median_pf / positive_windows / negative_windows / total_pnl /
   max_drawdown_max / group_prior10 / group_oos5 / verdict）と `DIAGNOSTIC_SUMMARY_REQUIRED_KEYS`
   （best_oos_rule / best_oos / oos5_majority_acc / oos_margin_vs_majority / verdict）を定義し、
   `validate_summary_schema(summary, required_keys=...)`（presence-only・値は不問・ValueErrorで不足キー報告）
   を追加。全7ランナーの `write_json(summary)` 直前で検証を呼ぶ（戦略系は既定、regimeは診断schema）。
   出力内容は不変。戦略系と診断系で構造が異なるため schema は2系統に分離。
4. 安全表示（safety_metadata）の単一ソース化
   — **着手済み**: 全7ランナーの manifest が `**safety_metadata()`（6フラグ）を持つよう統一。
   旧4戦略ランナー（rsi_final/breakout/bollinger/market_structure）はベタ書き3フラグを
   `**safety_metadata()` に置換し、`real_order`/`private_api_used`/`api_key_used` を完備
   （既存3キーは同値維持）。これで `report_index_entry().read_only_confirmed` が全 run で True。
5. レポート一覧UI / run詳細UI に備えたデータ構造整理
   — **着手済み**: `fx_eval_common` に read-only 純関数 `report_index_entry(run_dir)` を追加。
   1 run ディレクトリの manifest/warnings/単一 metrics_*_summary.json から一覧用メタ
   （run_id / kind / strategy / timeframe / cost_scenario / verdict / median_expectancy /
   median_pf / total_pnl / max_drawdown_max / created_at / summary_file / safety(6flags) /
   read_only_confirmed / safety_conflicts / warnings_count / has_warnings）を抽出。安全フラグは
   manifest∪warnings を fail-safe 統合（不明・矛盾は read_only_confirmed=False）。summary 0件→
   FileNotFoundError、複数→ValueError。ディレクトリ走査・UI実装はしない。
   （旧4戦略ランナーの safety 未記録は §4 で解消済み＝全 run で read_only_confirmed=True 可能。）
   さらに `list_report_index(exports_root)` を追加: exports_root 直下の各 run dir に
   report_index_entry() を適用し行リストを返す read-only 純関数。壊れた run（summary 0件/複数・
   JSON parse error・権限エラー等）は全体を止めず error 行（has_error=True / read_only_confirmed=
   False）にする。ソートは created_at 降順 → created_at 無し → error の順。exports_root が無い/
   非ディレクトリなら FileNotFoundError、空なら []。ディレクトリ走査のみで UI/API は作らない。
   加えて `format_report_index_markdown(rows)` を追加: list_report_index() の戻り値を
   人間/ChatGPT 用 Markdown 表に整形する read-only 純関数（ファイル/再計算なし）。列は
   status / run_id / kind / strategy / timeframe / cost / verdict / expectancy / pf /
   total_pnl / max_dd / safety / warnings / created_at / error。status は
   ERROR>CONFLICT>UNCONFIRMED>WARN>OK の1トークン、safety は read-only / conflict:keys /
   incomplete / unconfirmed、数値は固定小数（expectancy4・pf3・pnl/dd2）、None/空/欠損は `-`、
   セル内 `|` はエスケープ、空 rows はヘッダ＋区切り行のみ・末尾改行なし。
   さらに `validate_report_index_row(row, required_keys=...)` を追加: report index row の
   presence-only 検証（`validate_summary_schema` と同設計）。非Mapping/必須キー不足で
   ValueError（不足キー名を含む）、値・型・None/空は不問、追加キーは許容。正常行は
   `REPORT_INDEX_REQUIRED_KEYS`、error 行は `REPORT_INDEX_ERROR_REQUIRED_KEYS`（run_id /
   error / has_error / read_only_confirmed / created_at / summary_file）で検証し2系統に分離。
   `list_report_index()` は返却前に各行を該当 schema で検証（契約違反を早期検出）。
   `format_report_index_markdown()` は検証を強制せず欠損キー耐性を維持。
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
