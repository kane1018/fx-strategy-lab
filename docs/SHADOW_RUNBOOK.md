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

## 7. 次フェーズ

- Phase 2D / 2C-2: 1〜2 週間の注文なし運用ログ、run 結果の reports 化、複数日集計、より安全な停止条件。
- Phase 3: Private API の **read-only** 設計（残高/建玉の参照のみ・まだ注文なし）。APIキーの扱いは
  [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) の基準＋明示承認のうえ別フェーズ管理。
