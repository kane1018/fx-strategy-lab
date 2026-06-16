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
   加えて run 詳細用に `report_detail(run_dir)` を追加: 1 run の詳細データを集約する
   read-only 純関数。`report_index_entry()` を index として再利用し、manifest /
   warnings / 単一 metrics_*_summary.json を読み、run dir 直下のファイルを
   name / kind(json|csv|markdown|other) / size_bytes で一覧化（CSV 本文は読まない）、
   summary.md と *_final_decision.md の小さい Markdown 本文のみ UTF-8 で取り込む
   （サイズガード超過は本文 None・ファイル名は保持）。一覧用ファイルは
   files / metrics_files / csv_files / markdown_files に分類。複数 run を扱う
   list_report_index と違い個別 run の壊れは例外（run_dir 無/非dir→FileNotFoundError、
   summary 0件→FileNotFoundError、複数→ValueError、JSON 破損→JSONDecodeError）。
   詳細契約は `REPORT_DETAIL_REQUIRED_KEYS` と `validate_report_detail(detail)`
   （presence-only・他の validate 系と同設計）で固定。実 analysis_exports は読まず
   tmp_path のみでテスト。UI/API は作らない。
   加えて `format_report_detail_markdown(detail)` を追加: report_detail() の戻り値を
   人間/ChatGPT 用の1 run詳細 Markdown に整形する read-only 純関数（ファイル/再計算なし）。
   セクションは Overview / Safety / Metrics Summary / Cost / Execution / Files /
   Summary Markdown / Final Decision。各表は key|value（Files は name|kind|size_bytes）、
   数値は固定小数（expectancy4・pf3・pnl/dd2）、dict/list セルは compact JSON、
   None/空/欠損は `-`、セル内 `|` はエスケープ。summary.md / *_final_decision.md 本文は
   セクション本文として埋め込み（無ければ `-`）、CSV/JSON 本文は表示しない。
   `validate_report_detail` は強制せず欠損キー耐性を維持。末尾改行なし。
   一覧用 `format_report_index_markdown` と対で「一覧→詳細」両方が ChatGPT に貼れる。
6. E2E導入候補フローの docs 化（§11）
   — **着手済み**: §11 を index/detail 関数群（list_report_index / report_index_entry /
   validate_report_index_row / format_report_index_markdown / report_detail /
   validate_report_detail / format_report_detail_markdown / safety_metadata）に対応づけて
   具体化。E2E前提・ユーザーフロー・関数⇔画面対応表・安全/一覧/詳細/禁止の確認項目・
   E2Eテストケース候補（E2E-01〜08）・E2Eが判定しない範囲を確定。コード/UI/API は作らない。

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

index/detail 系の read-only 関数（`list_report_index` / `report_index_entry` /
`validate_report_index_row` / `format_report_index_markdown` / `report_detail` /
`validate_report_detail` / `format_report_detail_markdown` / `safety_metadata`）が
出揃ったので、最初の E2E が対象にするユーザーフローと確認項目をここで確定する。
本節は **docs 確定のみ**で、UI/API/E2E の実装は含まない。

### 11-1. E2E導入前の前提（今回の境界）

- E2E はまだ導入しない（Playwright/Cypress も入れない）。
- UI も API もまだ実装しない。今回は **E2E 対象フローの docs 確定のみ**。
- 実注文なし / Private API なし / APIキー・secret なし。
- `.env` の表示・変更なし。実 `analysis_exports/` の読み込みなし。
- 新戦略検証なし / 追加バックテストなし / コード変更なし。

### 11-2. 最初のE2Eで守るべきユーザーフロー（将来）

```text
レポート一覧を開く
↓
run一覧が表示される
↓
read-only / no real order / no private api / api key unused / order disabled が
  安全バッジとして見える
↓
verdict / expectancy / PF / total_pnl / max_dd / warnings が見える
↓
壊れたrunがある場合は ERROR 行として見える
↓
任意のrunを選択する
↓
run詳細が表示される
↓
Overview / Safety / Metrics Summary / Cost / Execution / Files /
  Summary Markdown / Final Decision が見える
↓
CSV本文は勝手に読み込まれず、ファイル一覧またはダウンロード導線として扱われる
↓
実注文・Private API・APIキー入力・market_order の導線が存在しない
```

### 11-3. 関数と画面の対応表

| 将来の画面/処理 | 支える関数 | 役割 |
| --- | --- | --- |
| レポート一覧データ | `list_report_index(exports_root)` | 複数runをread-onlyで一覧化（壊れたrunはerror行） |
| 一覧1行 | `report_index_entry(run_dir)` | 1 runの代表メタ＋安全フラグを抽出 |
| 一覧row契約 | `validate_report_index_row(row)` | UIが前提にするキーを presence-only 検証 |
| 一覧Markdown | `format_report_index_markdown(rows)` | ChatGPT貼り付け用の一覧表 |
| run詳細データ | `report_detail(run_dir)` | 1 runの詳細データ（index/manifest/warnings/summary/files）を集約 |
| run詳細契約 | `validate_report_detail(detail)` | 詳細画面が前提にするキーを presence-only 検証 |
| 詳細Markdown | `format_report_detail_markdown(detail)` | ChatGPT貼り付け用の詳細レポート |
| 安全メタ | `safety_metadata()` | read-only / no order 系 6フラグの単一ソース |
| 一覧キー契約 | `REPORT_INDEX_REQUIRED_KEYS` / `REPORT_INDEX_ERROR_REQUIRED_KEYS` | 正常行/error行の必須キー定義 |
| 詳細キー契約 | `REPORT_DETAIL_REQUIRED_KEYS` | 詳細dictの必須キー定義 |
| 安全キー契約 | `REPORT_INDEX_SAFETY_KEYS` | 検証対象の6安全フラグ名 |

### 11-4. E2Eで確認すべき安全表示

- `read_only_confirmed = True`
- `real_order = False`
- `private_api_used = False`
- `api_key_used = False`
- `gmo_readonly = True`
- `gmo_order_enabled = False`
- `no_order_execution = True`
- `safety_conflicts = []`
- safety incomplete / conflict / error run は **安全扱いしない**
  （`read_only_confirmed=False` のまま、UNCONFIRMED / CONFLICT / ERROR として表示）。

### 11-5. E2Eで確認すべき一覧項目（`format_report_index_markdown` の列）

- status / run_id / kind / strategy / timeframe / cost / verdict /
  expectancy / PF / total_pnl / max_dd / safety / warnings / created_at / error

### 11-6. E2Eで確認すべき詳細項目（`format_report_detail_markdown` のセクション）

- Overview / Safety / Metrics Summary / Cost / Execution / Files /
  Summary Markdown / Final Decision

### 11-7. E2Eで「存在しないこと」を確認する項目

- 実注文ボタンが存在しない
- GMO Private API 接続導線が存在しない
- APIキー入力欄が存在しない
- `.env` 表示導線が存在しない
- market_order 有効化導線が存在しない
- CSV 巨大本文を勝手に全展開しない（一覧 or ダウンロード導線に留める）
- DB 直接操作導線が存在しない

### 11-8. E2E導入の前にまだ必要なもの

- read-only API にするか、静的 Markdown 表示にするかの方針決定
- レポート一覧UI の MVP 仕様
- run詳細UI の MVP 仕様
- safety badge 表示ルール（True/False/conflict → バッジ・色）
- error row 表示ルール（ERROR 行の見せ方）
- cost metadata 表示ルール（spread/slippage/SL/TP のレイアウト）
- CSV ダウンロード/プレビュー方針（先頭N行プレビューの要否）
- E2Eツール選定
- 最初のE2Eテストケース定義（次項）

### 11-9. 最初のE2Eテストケース候補

```text
E2E-01: レポート一覧が表示される
E2E-02: 正常runに安全バッジ（read-only等）が表示される
E2E-03: error run が ERROR として表示される
E2E-04: run詳細へ遷移できる
E2E-05: 詳細画面に Overview/Safety/Metrics/Cost/Files/Summary/Final Decision が表示される
E2E-06: 実注文・Private API・APIキー入力導線が存在しない
E2E-07: CSV本文が勝手に全展開されない
E2E-08: safety conflict / incomplete は安全扱いされない
```

### 11-10. E2Eは何を判定しないか

- 戦略が勝てるかは判定しない
- 期待値が正しいかを再計算しない
- バックテストを再実行しない
- GMO API からデータ取得しない
- 実注文可否を試さない
- Private API 接続を試さない

## 12. E2Eで確認すべき安全項目

- `real_order = false` / `private_api_used = false` / `api_key_used = false`
- `gmo_readonly = true` / `gmo_order_enabled = false` / `no_order_execution = true`
- 画面・API応答に APIキー / secret / `.env` 値が出ないこと
- 実注文ボタン・Private API 実行導線が存在しない、または無効であること

## 13. 表示レイヤ方針（意思決定）

### 13-1. この決定の目的

- E2E に進む前に、レポート一覧・詳細を **どう表示するか** を1つに決める。
- 現在は index/detail のデータ関数（`list_report_index` / `report_detail`）と
  Markdown 整形関数（`format_report_index_markdown` / `format_report_detail_markdown`）が
  揃っている。次は UI/API 実装に入る前の分岐点。
- 表示レイヤは **実注文・Private API と完全に分離**する。
- 最初の表示レイヤは **read-only に限定**する（書き込み・注文・残高取得を一切持たない）。

### 13-2. 比較する2案

**A. read-only API 方式**

```text
GET /reports                  -> list_report_index(exports_root)
GET /reports/{run_id}         -> report_detail(run_dir)
GET /reports/markdown         -> format_report_index_markdown(rows)
GET /reports/{run_id}/markdown-> format_report_detail_markdown(detail)
```

- 既存の dict 返却関数とそのまま噛み合う。
- 将来の UI と E2E に直結する。safety metadata を API レスポンスとして扱いやすい。
- error row / safety conflict / incomplete を画面で扱いやすい。
- API レスポンスを E2E で検証しやすい。
- ただし endpoint 設計が必要。認証・アクセス制御・ローカル限定方針を後で決める必要がある。

**B. 静的 Markdown 表示方式**

```text
list_report_index → format_report_index_markdown → .md として保存/表示
report_detail     → format_report_detail_markdown → .md として保存/表示
```

- 実装が軽い。ChatGPT へ貼りやすい。サーバー/UI 不要。
- ただし 一覧→詳細 の操作導線を E2E しにくい。
- safety badge / error row の UI 表現へ発展しにくい。画面化時に作り直しが発生しやすい。

### 13-3. 比較表

| 観点 | A: read-only API | B: 静的Markdown |
| --- | --- | --- |
| 既存関数との相性 | ◎ dict をそのまま返せる | ○ formatter をそのまま使える |
| UI化のしやすさ | ◎ 一覧/詳細に直結 | △ 画面化で作り直し |
| E2Eのしやすさ | ◎ レスポンス/遷移を検証可 | △ 操作導線が乏しい |
| ChatGPT相談のしやすさ | ○ /markdown で両立 | ◎ そのまま貼れる |
| 安全表示の扱いやすさ | ◎ badge へ展開しやすい | △ テキスト止まり |
| error rowの扱いやすさ | ◎ 行として明示しやすい | △ 表現が限定 |
| CSV巨大本文を避けやすいか | ◎ API契約で本文を返さない | ○ formatter が出さない |
| 実装の軽さ | △ endpoint 設計が要る | ◎ 最軽量 |
| 将来の拡張性 | ◎ UI/E2E/フィルタへ伸びる | △ 頭打ち |
| 実注文からの分離 | ◎ read-only 専用で隔離 | ◎ そもそも実行系なし |
| 推奨度 | ◎ Primary | ○ Supporting |

### 13-4. 推奨方針

**A: read-only API 方式を採用**する。

- すでに `list_report_index()` / `report_detail()` が UI/API 向けの dict を返す。
- `format_*_markdown()` は ChatGPT 貼り付け用の補助として残せる（/markdown で両立）。
- 将来の一覧UI・詳細UI・E2E に直結する。
- safety metadata をバッジ表示へ展開しやすい。
- error row / safety conflict を画面上で明示しやすい。
- CSV 本文を読まない設計を API 側で守りやすい。
- §11 の「最初のE2E対象フロー」と整合する。

### 13-5. 採用する構成

```text
Primary:      read-only API
Supporting:   Markdown formatter for ChatGPT / human review
Not primary:  static Markdown only
```

### 13-6. 最初の read-only API MVP 範囲（将来・今回は実装しない）

```text
GET /reports
  - list_report_index(exports_root) の結果を返す
  - 実注文・Private API・APIキー入力導線なし
  - error run も error row として返す

GET /reports/{run_id}
  - report_detail(run_dir) の結果を返す
  - summary.md / final_decision.md は detail 内に含む
  - CSV 本文は返さない（files 一覧だけ返す）

GET /reports/markdown
  - format_report_index_markdown(list_report_index(exports_root)) を返す

GET /reports/{run_id}/markdown
  - format_report_detail_markdown(report_detail(run_dir)) を返す
```

### 13-7. read-only API で絶対にやらないこと

- 実注文しない / GMO Private API に接続しない
- APIキー/secret を扱わない / `.env` を表示しない
- market_order を有効化しない / DB を直接操作しない
- CSV 巨大本文を返さない / analysis_exports を書き換えない
- バックテストを再実行しない / GMO API から新規データ取得しない
- 口座残高を取得しない / 注文・決済・建玉取得の導線を作らない

### 13-8. E2E との対応（§11）

- `GET /reports` が E2E-01〜03 を支える
- `GET /reports/{run_id}` が E2E-04〜05 を支える
- API/画面に危険導線がないことが E2E-06 を支える
- CSV 本文を返さないことが E2E-07 を支える
- safety conflict / incomplete を安全扱いしないことが E2E-08 を支える

### 13-9. 次に進む条件

```text
次は「read-only API MVP仕様」を docs 化する。
まだ API 実装には入らない。
MVP仕様で endpoint / response shape / error response / safety badge mapping / tests を決める。
その後に初めて実装へ進む。
```

### 13-10. 今回（§13 追加）はやらないこと

- API 実装しない / UI 実装しない / E2E 導入しない
- package 追加しない / 既存コード変更しない
- 実 analysis_exports を読まない / 新戦略検証しない / バックテストしない
- 実注文・Private API・APIキー・`.env` に触れない

## 14. read-only API MVP 仕様

§13 で Primary = read-only API に決定したので、FastAPI 実装に入る前に endpoint /
レスポンス shape / エラー方針 / 安全表示 / テスト方針をここで確定する。本節は **仕様 docs のみ**で、
API/UI/E2E の実装は含まない。

### 14-1. read-only API MVP の目的

- レポート一覧・run詳細を UI/E2E から安全に参照するための薄い API。
- 既存の `list_report_index()` / `report_detail()` / `format_*_markdown()` を API に載せるだけ
  （値の再計算をしない）。
- バックテストや GMO API 取得は行わない。
- 実注文・Private API・APIキー入力・口座情報取得は扱わない。
- 最初の API は **ローカル/開発用の read-only 表示レイヤに限定**する。

### 14-2. MVP エンドポイント

```text
GET /reports
GET /reports/{run_id}
GET /reports/markdown
GET /reports/{run_id}/markdown
```

### 14-3. GET /reports

- 目的: 複数 run の一覧を返す。
- 内部利用: `list_report_index(exports_root)`

```json
{
  "items": [
    {
      "status": "OK",
      "run_id": "...",
      "kind": "...",
      "strategy": "...",
      "timeframe": "...",
      "cost_scenario": "...",
      "verdict": "...",
      "median_expectancy": 0.0164,
      "median_pf": 1.016,
      "total_pnl": 56.95,
      "max_drawdown_max": 65.46,
      "created_at": "...",
      "summary_file": "...",
      "safety": {
        "real_order": false,
        "private_api_used": false,
        "api_key_used": false,
        "gmo_readonly": true,
        "gmo_order_enabled": false,
        "no_order_execution": true
      },
      "safety_complete": true,
      "safety_conflicts": [],
      "read_only_confirmed": true,
      "warnings_count": 0,
      "has_warnings": false,
      "has_error": false
    }
  ],
  "count": 1
}
```

- `status` は §11-5 / safety badge（§14-10）に対応する1トークン。
- error row も `items` に含める（`has_error=true`）。`has_error=true` は **安全扱いしない**。
- CSV 本文は返さない。実 run の再計算はしない。

### 14-4. GET /reports/{run_id}

- 目的: 1 run の詳細データを返す。
- 内部利用: `report_detail(run_dir)`

```json
{
  "run_id": "...",
  "index": {"...": "report_index_entry 相当"},
  "manifest": {"...": "manifest.json"},
  "warnings": {"...": "warnings.json"},
  "summary": {"...": "metrics_*_summary.json"},
  "summary_file": "...",
  "summary_markdown_file": "summary.md",
  "summary_markdown": "...",
  "final_decision_file": "...",
  "final_decision_markdown": "...",
  "files": [
    {"name": "metrics_by_window.csv", "kind": "csv", "size_bytes": 12345}
  ],
  "metrics_files": ["..."],
  "csv_files": ["..."],
  "markdown_files": ["..."]
}
```

- CSV 本文は返さない。JSON/Markdown は既存 `report_detail()` の範囲のみ。
- summary.md / final_decision.md は detail に含める。safety は `index` 内を参照する。
- 実注文系情報は返さない。

### 14-5. GET /reports/markdown

- 目的: ChatGPT 貼り付け用の一覧 Markdown を返す。
- 内部利用: `format_report_index_markdown(list_report_index(exports_root))`

```json
{ "markdown": "| status | run_id | ... |" }
```

- Markdown は補助用途。UI の Primary data source は `/reports` の JSON。実ファイル生成はしない。

### 14-6. GET /reports/{run_id}/markdown

- 目的: ChatGPT 貼り付け用の1 run詳細 Markdown を返す。
- 内部利用: `format_report_detail_markdown(report_detail(run_dir))`

```json
{ "markdown": "# FX Report Detail: ..." }
```

- Markdown は補助用途。UI の Primary data source は `/reports/{run_id}` の JSON。実ファイル生成はしない。

### 14-7. run_id 解決方針

- `run_id` はディレクトリ名として扱う。
- `..` や `/` を含む値は禁止。URL decode 後もパストラバーサルを許可しない。
- `(exports_root / run_id).resolve()` が `exports_root.resolve()` 配下であることを確認する
  （配下でなければ 400）。
- 存在しない run は 404。
- 許可パターン（既存 run_id は `YYYYMMDD_HHMMSS_gmo_public_paper_<kind>` 形式に合致）:

```text
^[A-Za-z0-9_.-]+$
```

  併せて、`.` 単体 / `..` / 先頭 `.`（隠し）/ パス区切りを含むものは拒否（安全側）。

### 14-8. exports_root 解決方針

- MVP では exports_root を **サーバー側で明示設定**する（例: 設定値 or 起動時パラメータ）。
- `.env` の表示・編集はしない。実装時に安全なデフォルトを決める。
- API から exports_root を任意指定させない（クエリで任意パスを渡させない）。
- サーバー側で固定された root のみ読む。
- root が存在しない場合は **503 Service Unavailable**（推奨）。
  理由: API 自体は存在するが、レポート保存先設定が未準備だから（5xx=サーバー側都合）。

### 14-9. エラーレスポンス方針

| ケース | ステータス | 方針 |
| --- | ---: | --- |
| exports_root 未設定/不存在 | 503 | 設定未準備（サーバー側都合） |
| run_id 不正（traversal/パターン外） | 400 | 入力不正 |
| run_id が存在しない | 404 | 対象なし |
| summary 0件/複数 | 422 | run構造不正 |
| JSON 破損 | 422 | run構造不正 |
| 予期しない例外 | 500 | 未分類エラー |

- エラー本文は `{ "detail": "...", "code": "..." }` 程度の最小形。
- 安全情報をエラー本文に入れる場合も、**不明な安全状態を安全扱いしない**
  （成功レスポンスの safety は run 由来、エラー時は安全フラグを `true` で詐称しない）。

### 14-10. safety badge mapping

| 条件 | badge | 意味 |
| --- | --- | --- |
| read_only_confirmed=true and safety_conflicts=[] | SAFE_READ_ONLY | 安全確認済み |
| has_error=true | ERROR | 壊れた run |
| safety_conflicts not empty | SAFETY_CONFLICT | 安全メタ矛盾 |
| safety_complete=false | SAFETY_INCOMPLETE | 安全メタ不足 |
| read_only_confirmed=false | UNCONFIRMED | read-only 未確認 |

- 優先順位は ERROR > SAFETY_CONFLICT > SAFETY_INCOMPLETE > UNCONFIRMED > SAFE_READ_ONLY。
- conflict / incomplete / error / unconfirmed は **安全扱いしない**。
- バッジ表示は UI 実装時に使う（`format_report_index_markdown` の status と整合）。今回は docs のみ。

### 14-11. cost metadata mapping

- 一覧（`/reports`）で表示: cost_scenario / timeframe
- 詳細（`/reports/{run_id}`）で表示: cost_scenario / timeframe / spread_pips /
  slippage_pips / stop_loss_pips / take_profit_pips / symbols
- CSV 本文や再計算はしない。

### 14-12. CSV 方針

- `/reports` では CSV 本文を返さない。
- `/reports/{run_id}` でも CSV 本文を返さない（files 一覧に name/kind/size_bytes のみ）。
- CSV プレビューは MVP 外。
- CSV ダウンロードも MVP 外（必要なら別 endpoint として後で検討）。
- 巨大 CSV を自動展開しないことは E2E 対象（§11-7 / E2E-07）。

### 14-13. 想定テスト（将来の API 実装時）

```text
API-01: GET /reports returns items/count
API-02: GET /reports includes error rows
API-03: GET /reports does not include CSV body
API-04: GET /reports/{run_id} returns detail
API-05: GET /reports/{run_id} rejects invalid run_id
API-06: GET /reports/{run_id} returns 404 for missing run
API-07: broken run returns 422
API-08: markdown endpoints return markdown string
API-09: safety badge mapping handles SAFE/ERROR/CONFLICT/INCOMPLETE/UNCONFIRMED
API-10: no endpoint exposes order/private/api-key/.env behavior
```

- テストは tmp_path に作った run dir を exports_root に向けて行い、実 analysis_exports は読まない。

### 14-14. 実装に進む前のチェックリスト

- 既存 FastAPI アプリの構成（app 生成箇所・既存ルーター登録方法）確認
- ルーターを追加する場所（例: `app/routers/`）の確認
- exports_root の設定方法（設定値/起動パラメータ）確認
- API レスポンスモデルを Pydantic で定義するか、dict をそのまま返すか判断
- ローカル限定/認証方針（bind 先・公開しない方針）確認
- 既存テスト構成（pytest 配置・fixtures）確認
- 実 analysis_exports を読まないテスト方針（tmp_path）確認
- 危険導線（注文/Private API/APIキー/.env）を追加しない確認

### 14-15. 今回（§14 追加）はやらないこと

- API 実装しない / UI 実装しない / E2E 導入しない
- package 追加しない / 既存コード変更しない
- 実 analysis_exports を読まない / 新戦略検証しない / バックテストしない
- 実注文・Private API・APIキー・`.env` に触れない

### 14-16. read-only API 実装準備メモ（既存FastAPI構成の調査）

`/reports` 系 read-only API を実装する前に、既存 backend の FastAPI 構成を read-only で調査し、
ルーター追加位置・exports_root の扱い・テスト配置・危険導線との分離を確定する。**本節は調査 docs のみ**
で、コード変更・API 実装は含まない。調査は `backend/app/` のソース構造のみを対象とし、`.env` の中身・
secret・実 analysis_exports は読んでいない。

#### 14-16-1. 調査目的

- `/reports` 系 read-only API 実装前に既存 FastAPI 構成を把握する。
- ルーター追加位置を決める / exports_root 設定方針を決める / APIテスト配置を決める。
- 既存の危険導線（注文・broker 接続テスト等）と完全分離する。

#### 14-16-2. FastAPI app 構成（調査結果）

| 項目 | 調査結果 |
| --- | --- |
| app生成ファイル | `backend/app/main.py` |
| app変数名 | `app`（`app = FastAPI(title="FX Strategy Lab API", version="0.1.0", lifespan=lifespan)`） |
| 起動ファイル | `app/main.py`（uvicorn 起動想定。`uvicorn[standard]` は requirements にあり） |
| 既存prefix | 大半が `/api/...`、ヘルスのみ `/health`（共通 prefix 変数は未使用） |
| 既存middleware | CORSMiddleware（`allow_origins=[settings.frontend_origin]`） |
| 既存CORS | あり（frontend_origin 1件、methods/headers `*`、credentials 有効） |
| 既存router登録方法 | **`APIRouter` / `include_router` は未使用**。全 endpoint を `@app.get/post` で main.py に直接定義 |

#### 14-16-3. 既存ルーター構成（調査結果）

| 既存router | ファイル | prefix | tags | 備考 |
| --- | --- | --- | --- | --- |
| （専用 APIRouter なし） | `app/main.py` | `/api` ＋ `/health` | なし | endpoint をデコレータで直接定義 |

主な既存 endpoint 群（参考）: `/health`、`/api/backtests`、`/api/paper/...`、`/api/signals/...`、
`/api/broker/connection-test`、`/api/orders`（POST/GET/close）、`/api/bot/...`、`/api/automation/...`。

`/reports` 系ルーターの追加候補（**今回はファイル作成しない**）:

```text
backend/app/routers/__init__.py   # 新規ディレクトリ（初の APIRouter 化）
backend/app/routers/reports.py    # APIRouter(tags=["reports"])
main.py で app.include_router(reports.router)
```

- 既存は main.py 直書きだが、`/reports` 系は **新規 APIRouter として分離**するのを推奨
  （注文系と物理的に別ファイルになり、安全分離が明確）。
- **パスの整合に関する未決事項**: §14 は `/reports` を採用しているが、既存規約は `/api/...`。
  実装時に「§14 どおり `/reports`」か「既存に合わせ `/api/reports`」かを1つ決める。
  推奨は **`/api/reports` 系**（既存規約・CORS・将来の UI フェッチと一貫）。決定後 §14-2 を追従更新する。

#### 14-16-4. config / settings 構成（調査結果）

- 設定は `app/config.py` の `Settings(BaseSettings)`（pydantic-settings、`get_settings()` で取得）。
- `model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")`。
  既に `enable_live_trading=False` / `gmo_fx_readonly=True` / `gmo_fx_order_enabled=False` と安全側。
- **exports_root（analysis_exports の場所）の設定は未定義** → 実装時に `Settings` へ
  `analysis_exports_root: str`（安全なデフォルト付き）を追加するのが自然。
- exports_root 方針: API から任意パス指定させない / query で root を渡さない /
  サーバー側固定設定（`get_settings()` 由来）/ `.env` の中身は表示しない /
  テストでは tmp_path を root として注入できるようにする（依存注入 or settings override）/
  root 不存在は §14-8 どおり 503。

#### 14-16-5. API 実装候補（将来・今回はファイル作成しない）

```text
app/routers/reports.py
  GET /reports                  -> list_report_index(exports_root)
  GET /reports/{run_id}         -> report_detail(run_dir)
  GET /reports/markdown         -> format_report_index_markdown(...)
  GET /reports/{run_id}/markdown-> format_report_detail_markdown(...)
（パス prefix は 14-16-3 の未決事項に従う。GET のみ）
```

#### 14-16-6. テスト配置候補

| テスト種別 | 配置候補 | 内容 |
| --- | --- | --- |
| API一覧テスト | `app/tests/test_reports_api.py` | GET /reports（items/count・error行・CSV本文なし） |
| API詳細テスト | `app/tests/test_reports_api.py` | GET /reports/{run_id}（detail・safety は index 内） |
| markdownテスト | `app/tests/test_reports_api.py` | /markdown 2本（markdown 文字列を返す） |
| error responseテスト | `app/tests/test_reports_api.py` | 400 / 404 / 422 / 503 |
| safetyテスト | `app/tests/test_reports_api.py` | 注文/Private/APIキー/.env 導線が無いこと |

- テストは `from fastapi.testclient import TestClient` を使用（既存 deps の fastapi + httpx で動く）。
- run dir は **tmp_path に生成**し、その root を exports_root に注入。実 analysis_exports は読まない。
- 既存命名規則 `test_*.py` / `test_*` 関数、pytest、`conftest.py` の `db` fixture と同じ流儀。

#### 14-16-7. §14-14 実装前チェックリストへの回答

- 既存FastAPIアプリの構成確認: **済**。`app/main.py` の `app`、全 endpoint デコレータ直書き、CORS あり。
- ルーターを追加する場所の確認: **`app/routers/reports.py` を新規**（初の APIRouter 化）＋ main.py で include。
- exports_rootの設定方法確認: `Settings` に `analysis_exports_root` を追加（pydantic-settings、固定・API指定不可）。
- APIレスポンスモデルをPydanticで定義するか判断: MVP は **dict 直返しで可**（list/detail は既に整形済み dict）。
  将来 UI/OpenAPI 強化時に Pydantic レスポンスモデルへ移行（任意）。
- ローカル限定/認証方針確認: 既存に認証なし。MVP は **ローカル開発用・read-only**、127.0.0.1 バインド前提。
  本格認証は §14 の範囲外（後日）。
- 既存テスト構成確認: **済**。`app/tests/`、pytest、`db` fixture。TestClient は未使用だが追加依存なしで導入可。
- 実analysis_exportsを読まないテスト方針確認: **tmp_path で run dir を作る**方針で確定。
- 危険導線を追加しない確認: `/reports` 系は GET read-only のみ。注文/broker/automation には触れない。

#### 14-16-8. 次に実装する場合の最小方針

- まず `/reports` 系 router **だけ**追加する。既存注文系・GMO Private API・OANDA・RiskManager に触らない。
- endpoints は **GET のみ**。POST/PUT/DELETE は作らない。
- 実バックテスト・GMO API 取得は行わない。`analysis_exports/` は読み取りのみ。
- CSV 本文は返さない。tests は tmp_path で作る。`TestClient`（既存 deps）を使う。追加依存なし。

#### 14-16-9. 危険導線の現状（分離対象として記録）

既存 main.py に以下の書き込み/実行系が既にある（**今回は変更しない**。`/reports` 系と完全分離する）:
`/api/orders`（POST place_order）, `/api/orders/{id}/close`, `/api/broker/connection-test`,
`/api/bot/start|stop`, `/api/automation/start|cycle|stop`。
これらは read-only レポート API とは別系統であり、`/reports` 系からは参照も呼び出しもしない。
なお APIキー/secret を返す導線・`.env` を表示する導線・market_order を有効化する導線は確認されなかった。

#### 14-16-10. まだ決めないこと

- UIデザイン / E2Eツール / 認証の本格設計 / CSVプレビュー / CSVダウンロード /
  本番公開 / 実注文連携 / Private API連携 / paper forward。
