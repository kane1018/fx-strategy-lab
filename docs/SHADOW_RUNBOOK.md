# Shadow Run Runbook（Phase 2C・local-only）

GMO Public（または mock）の相場データで **注文なし**の shadow run をローカル実行し、events/summary を
保存する手順。実注文・実資金・Private API・APIキー・`.env` は使わない。出力 `shadow_exports/` は
**コミット禁止**（gitignore 済み）。設計は [PHASE2_SHADOW_TRADING_PLAN.md](PHASE2_SHADOW_TRADING_PLAN.md)、
Public API 仕様は [GMO_PUBLIC_API_PLAN.md](GMO_PUBLIC_API_PLAN.md)。

## 1. Phase 2C の範囲

- local shadow run CLI（mock / gmo-public）、最小 SignalFn、shadow log 保存、summary 集計、offline テスト。
- 本番公開なし（`app.main_readonly:app` に追加しない）。注文なし・Private API/APIキー禁止。

## 2. 実行方法

```bash
cd backend

# ヘルプ
python -m scripts.run_shadow_session --help

# mock（ネットワーク不要・deterministic）
python -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 20

# GMO Public（read-only・認証不要。市場時間/日付により失敗しうる。失敗時は mock を使う）
python -m scripts.run_shadow_session --source gmo-public --symbol USD_JPY \
    --interval M1 --date 20260618 --steps 5
```

- `--steps` で必ず上限を持つ（無限ループなし）。`--units` / `--max-units` で virtual ロットと停止閾値。
- `--out-root` 既定 `shadow_exports`（=`backend/shadow_exports/`）。**生成物は git add しない**。

## 3. 出力ファイル構成

```text
shadow_exports/<run_id>/
  events.jsonl    # 1 step 1 行（signal / virtual_order / position / virtual_pnl / safety ...）
  summary.json    # run 集計（下記）
  metadata.json   # run パラメータ + safety + 注意書き
```

- run_id 例: `YYYYMMDD_HHMMSS_shadow_USD_JPY_mock`。
- **実 API レスポンスの生データは保存しない**（内部正規化済みの event/summary のみ）。

## 4. summary の主項目

run_id / source / symbol / interval / steps_requested / steps_executed / events_count /
virtual_orders_count / buy_count / sell_count / flat_count / max_abs_units /
final_position_side / final_position_units / final_average_price / final_unrealized_pnl /
last_price / data_points / halted / halt_reason / safety / created_at。

## 5. SignalFn について

`app/shadow/signals.py` の `momentum_signal`（last close > prev → buy、< → sell、== → flat）は
**動作確認用の最小シグナルであり、収益性判断のための戦略ではない**。パラメータ最適化や戦略研究はしない。

## 6. safety 制約

- 各 event/summary に `shadow_safety()`: `real_order=false` / `private_api_used=false` /
  `api_key_used=false` / `no_order_execution=true` / `live_trading_environment_enabled=false` /
  `gmo_readonly=true` / `gmo_order_enabled=false`。
- 注文送信関数なし。`VirtualOrder(real_order=True)` は拒否。`units > max_units` で halt（以降ポジション不変）。
- gmo-public は Public GET のみ・認証ヘッダ無し・Private フォールバックなし・取得失敗は明示エラー。

## 6b. 複数 run の集計（Phase 2D・local-only）

`shadow_exports/` 配下の複数 run の `summary.json` を読み込み、合計/グループ集計・safety 違反検出を行う。
ネットワーク不要・APIキー不要・実注文なし。入力も出力も `shadow_exports/`（gitignore・**commit 禁止**）。

```bash
cd backend
python -m scripts.summarize_shadow_runs --help
# 標準出力に Markdown レポート
python -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
# 標準出力に runs CSV
python -m scripts.summarize_shadow_runs --input-root shadow_exports --format csv
# ファイル出力（aggregate.json/.md, runs.csv, by_symbol.csv, by_date.csv）
python -m scripts.summarize_shadow_runs --input-root shadow_exports --out shadow_exports/aggregate
```

- 集計: runs_count / sources / symbols / intervals / total_* (steps/events/orders/buy/sell/flat) /
  total_final_unrealized_pnl / halted_runs_count / max_abs_units_overall / created_at 範囲 /
  by_source・by_symbol・by_interval・by_date。
- **safety 違反検出**: 各 run の safety が read-only 期待値（real_order=false / private_api_used=false /
  api_key_used=false / no_order_execution=true / live_trading_environment_enabled=false /
  gmo_order_enabled=false）を満たさないと `safety_violations` に記録し、CLI は警告＋exit code 2。
- 0 件・壊れた summary（JSON 破損/非オブジェクト）はスキップして件数を報告。入力 root 不在は明示エラー。
- 注: この集計は**安全性の継続確認が主目的**で、**収益性判断にはまだ不十分**（SignalFn は demo）。

## 7. 次フェーズ

- Phase 2D / 2C-2: 1〜2 週間の注文なし運用ログ、run 結果の reports 化、複数日集計、より安全な停止条件。
- Phase 3: Private API の **read-only** 設計（残高/建玉の参照のみ・まだ注文なし）。APIキーの扱いは
  [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) の基準＋明示承認のうえ別フェーズ管理。
