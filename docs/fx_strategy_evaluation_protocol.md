# 15窓 戦略評価プロトコル

今後の戦略を **同一条件で比較**するための標準評価基盤。M5 単純テクニカル研究フェーズ
（[fx_research_m5_summary.md](fx_research_m5_summary.md)）で確立した手順を、次フェーズ以降の
共通プロトコルとして固定する。

## 1. 目的

- 今後の戦略を同一の窓・固定条件・指標で比較し、戦略間で公平に判断する。
- IS（in-sample 10窓）/ OOS（out-of-sample 5窓）・symbol別・exit_reason別・market-state別で
  多面的に評価する。
- パラメータ探索や期間の都合の良い選び方を避け、過剰最適化を防ぐ。
- すべて GMO Public API read-only ペーパー。実注文・Private API・APIキーは使わない。

## 2. 標準window（15窓）

### prior10（in-sample）

| window | 期間 |
| --- | --- |
| window_1 | 2026-05-04〜2026-05-15 |
| window_2 | 2026-04-20〜2026-05-01 |
| window_3 | 2026-04-06〜2026-04-17 |
| window_4 | 2026-03-23〜2026-04-03 |
| window_5 | 2026-03-09〜2026-03-20 |
| window_6 | 2026-02-23〜2026-03-06 |
| window_7 | 2026-02-09〜2026-02-20 |
| window_8 | 2026-01-26〜2026-02-06 |
| window_9 | 2026-01-12〜2026-01-23 |
| window_10 | 2025-12-29〜2026-01-09 |

### oos5（out-of-sample）

| window | 期間 |
| --- | --- |
| oos_window_1 | 2025-12-15〜2025-12-26 |
| oos_window_2 | 2025-12-01〜2025-12-12 |
| oos_window_3 | 2025-11-17〜2025-11-28 |
| oos_window_4 | 2025-11-03〜2025-11-14 |
| oos_window_5 | 2025-10-20〜2025-10-31 |

> 祝日（2026-01-01 元日、2025-12-25 クリスマス）は klines が無く、window_10 と
> oos_window_1 はそれぞれ 9 営業日になる。これは正常で、warnings.json に記録される。

## 3. 標準固定条件

| 項目 | 値 |
| --- | --- |
| data source | GMO Public API klines (BID) |
| mode | read-only paper |
| timeframe | 原則 M5（次フェーズで別時間足を検証する場合は別枠で実施し混在させない） |
| cost_scenario | current_cost |
| spread_pips | 1.2 |
| slippage_pips | 0.2 |
| stop_loss_pips / take_profit_pips | 30 / 60 |
| exit_policy | baseline（反対シグナル + SL/TP） |
| symbols | USD_JPY / EUR_JPY / GBP_JPY / AUD_JPY |
| continuous replay | 有効 |
| real_order | No |
| private_api_used | No |
| api_key_used | No |

ルックアヘッド禁止: シグナルは確定足のみ（リプレイは `frame[:index]`、当該バーの open で
建玉）。当日終了後の情報や未来足を判定に使わない。

## 4. 必須評価指標

window ごと:

- 完了取引数、勝率、総損益、期待値、PF、最大DD、最大単発損失、最大連敗
- SL件数、SL率、TP件数、TP損益
- 反対シグナル決済件数・損益、forced_close_count・ratio
- symbol別成績、日別成績

15窓全体:

- 期待値中央値、PF中央値
- プラスwindow数、マイナスwindow数
- 期待値>0 かつ PF>1 のwindow数
- 完了取引数≥30 のwindow数
- 合計損益、最大DD最大値、最大DD / 合計損益
- 合計SL件数、SL率中央値、TP合計損益、SL合計損益、反対シグナル決済合計損益
- symbol別: 合計損益 / 期待値 / PF / window勝敗
- 単一window依存・単一symbol依存の有無
- prior10 vs oos5 の比較
- market-state別結果（low/medium/high DE、both_lose相当日、rsi_only_win相当日 など）

## 5. 分類ルール

### 継続検証候補（主検証として残す）

すべて満たす場合のみ:

- 期待値中央値 > 0
- PF中央値 > 1
- プラスwindow数が明確に過半
- 期待値>0 かつ PF>1 のwindow が過半
- 合計損益がプラス
- 最大DDが合計損益に対して重すぎない
- prior10 と oos5 の両方で極端に崩れない（符号反転がない）
- 単一window / 単一symbol 依存が強くない

### 研究用ベースライン（比較基準として保存）

- 一部に構造的なエッジがある（例: 特定の相場状態でプラス）
- ただし実運用候補としては弱い（OOS不安定、薄利、DD重いなど）
- 今後の比較基準として保存する価値がある
- 追加最適化は原則しない

### 撤退（主検証から外す）

いずれかに該当:

- 期待値中央値 <= 0
- PF中央値 <= 1
- OOSで崩れる
- 合計損益がマイナス
- DDが重すぎる
- 単一window / 単一symbol 依存が強い
- 追加調整が過剰最適化に近い

## 6. 禁止事項

- 良い結果が出るまでパラメータを探索しない。
- IS（prior10）だけで採用判断しない。必ず OOS5 で確認する。
- OOSで崩れた条件を、閾値変更で後から救わない。
- strategy 追加の前に、仮説と採用/却下条件を明文化する。
- `.env` や secret / APIキーを表示・変更・コミットしない。
- 実注文・Private API には進まない。
- `analysis_exports/`・`.db`・`.sqlite`・`trades.csv`・`open_positions.csv` 等の巨大/生成
  ファイルをコミットしない（コミットはコードとドキュメントのみ）。
- GMO Public API は `GMO_FX_READONLY=true` / `GMO_FX_ORDER_ENABLED=false` を前提にし、
  実注文・実決済・Private API 接続へ進まない。

## 7. 共通モジュールと既存ランナー

### 共通モジュール（標準の単一の置き場所）

`backend/scripts/fx_eval_common.py` が、本プロトコルで全ランナーが一致させるべき定義の
**唯一の置き場所**:

- `WINDOWS` — 標準15窓（label, start, end, group）、`window_groups()` / `group_labels()`
- `SYMBOLS` / `TIMEFRAME` / `SPREAD` / `SLIP` / `STOP_LOSS_PIPS` / `TAKE_PROFIT_PIPS` / `EXIT_POLICY`
- `fixed_config(**overrides)` — manifest/warnings 用の固定条件ブロック
- `safety_metadata()` — read-only 安全フラグ（real_order=False など）
- `run_id(kind)` — `YYYYMMDD_HHMMSS_gmo_public_paper_<kind>` 形式
- `classify_strategy(...)` — 継続検証候補 / 研究用ベースライン / 撤退 の3分類判定（純関数）
- `robustness_summary` / `_summarize` / `_weekdays` など集計helperの再エクスポート

今後の新しいランナー（別時間足など）は、これらを `fx_eval_common` から import すること。
`rsi_final_15window.py` は後方互換のため同じ名前を再エクスポートしている。

### 既存ランナー（参考）

`backend/scripts/` に、本プロトコルに沿った 15窓評価ランナーがある（read-only paper）:

- `rsi_final_15window.py` — rsi_reversal の15窓評価（共通定義は fx_eval_common を再エクスポート）
- `bollinger_15window.py` — Bollinger 平均回帰の15窓評価 + market-state別分解
- `breakout_15window.py` — breakout の15窓評価
- `market_structure_15window.py` — market-structure 平均回帰の15窓評価
- `market_state_diagnostics.py` — rsi/breakout の勝敗 × market state 診断
- `adx_filter_oos_ab.py` — ADXフィルタの OOS A/B（却下の根拠）
- `rsi_m15_15window.py` — **高時間足フェーズの初回**: rsi_reversal を M15 で同一15窓評価
  （`fixed_config(timeframe="M15")` を使用。SL/TP は比較のため M5 と同じ 30/60 で未調整）

### 高時間足フェーズ（別枠）

M5 研究は一区切り済み。別時間足（M15/M30/H1）は **別フェーズ**として 1戦略ずつ評価する。
共通 `fx_eval_common` の窓・コスト・安全条件・分類判定をそのまま使い、`fixed_config(timeframe=...)`
で時間足のみ上書きする。注意: SL/TP は時間足に対して固定値（30/60）のままだと高時間足では相対的に
タイトになり得る（SL率が上がる）。最初は素の状態で「時間足だけで改善するか」を見て、SL/TP の
時間足調整は過剰最適化を警戒して別途・厳格に扱う。

共通化の第一歩として標準定義・固定条件・安全メタデータ・分類判定を `fx_eval_common` に集約した。
取得・replay・CSV/summary 出力処理の共通化は次の候補（[fx_research_m5_summary.md](fx_research_m5_summary.md) §8）。

## 8. E2E導入タイミング

現時点では、検証ランナー・集計・レポート出力が中心であり、E2E は導入しない。

E2E を導入する目安は以下。

- レポート一覧画面がある
- run_id 詳細画面がある
- summary / metrics / warnings を画面で確認できる
- read-only / no private api / no real order の安全状態を画面で確認できる
- ユーザーがブラウザで検証結果を閲覧・比較できる

それまでは pytest / ruff を優先する。
