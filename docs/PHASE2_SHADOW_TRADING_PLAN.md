# Phase 2A: GMO Public API / shadow 検証の土台

read-only reports 公開版（v0.1）の次フェーズ。**いきなり実注文・Private API には進まず**、
GMO **Public** API（認証不要・価格/ローソク足）と**注文なしの shadow 検証**へ進むための設計と最小土台。
本書は設計と安全制約の定義であり、実 API 接続・本番公開・実注文は含まない。

関連: 公開/認証方針 [PUBLICATION_POLICY.md](PUBLICATION_POLICY.md)、現在地 [PROJECT_STATUS.md](PROJECT_STATUS.md)、
安全実装 [SAFETY.md](SAFETY.md)。

## 1. Phase 2A の範囲

- Public API 調査（endpoint/レスポンス形式は**公式仕様を確認してから**実装＝Phase 2B）。
- market data の正規化（外部形式 → 内部 `Candle` / `Ticker`）。
- shadow event 設計（signal → virtual order → virtual position → virtual PnL → safety → event）。
- virtual order / virtual position の型・モデル（**実注文ではないことを型で保証**）。
- mock/fixture ベースのテスト。
- **local-only**（本番 UI に出さない / Render 公開 API に追加しない）。

## 2. 今回作らないもの（Phase 2A の対象外）

- Private API / APIキー / secret / `.env` 利用。
- 実注文 / 実資金 / 注文・決済・建玉取得 / 注文エンドポイント。
- 本番公開 API（`app.main_readonly:app` への機能追加は**しない**）。
- 認証 / DB 本番化 / 自動売買 / 本番データ運用。
- 実 GMO Public API への接続実装（仕様確認後の Phase 2B）。

## 3. Public API と Private API の境界

| 区分 | 内容 | 本フェーズ |
| --- | --- | --- |
| **Public API** | 価格 / ティッカー / ローソク足 / 板（認証不要で取得できる情報） | 検討・正規化対象（接続は Phase 2B） |
| **Private API** | 残高 / 建玉 / 注文 / 約定 / 注文変更 / 取消（要認証） | **対象外・実装禁止** |

コード上も分離する: shadow パッケージ（`backend/app/shadow/`）は Public 由来の market data と
virtual（never-sent）オブジェクトのみを扱い、broker / Private / 注文系モジュールを import しない。

## 4. shadow 検証の流れ

1. Public market data を取得（Phase 2A は **mock**、Phase 2B で実 Public API）。
2. 内部の `Candle` / `Ticker` 形式へ正規化（`normalize_candles` / `normalize_ticker`）。
3. 戦略判定（`SignalFn: list[Candle] -> Signal`）を実行。
4. `Signal`（buy / sell / flat）を作る。
5. `VirtualOrder` を作る（**実注文は送らない**。`real_order=False` を構築時に強制）。
6. `VirtualPosition` を更新（simulated fill のみ）。
7. virtual PnL を計算（`unrealized_pnl(price)`）。
8. safety check（例: `units > max_units` で halt フラグ）。
9. `ShadowEvent` を出力（signal / virtual order / position snapshot / pnl / safety / halted）。
10. reports 化（`analysis_exports` への書き出し・UI 表示）は将来フェーズ。

## 5. safety 制約（shadow 全イベントで保証）

`shadow_safety()`（`app/shadow/models.py`）が各 `ShadowEvent` に付与:

- `real_order = false`
- `private_api_used = false`
- `api_key_used = false`
- `no_order_execution = true`
- `live_trading_environment_enabled = false`
- `gmo_readonly = true` / `gmo_order_enabled = false`

加えて構造的な保証:

- 本パッケージに**注文送信関数は存在しない**（submit/send なし）。
- `VirtualOrder(real_order=True)` は **ValueError** で拒否（live order に転用不可）。
- secret / APIキー / `.env` を読まない・要求しない。ネットワーク I/O なし（mock client のみ）。

## 6. 実装した最小土台（Phase 2A）

- `backend/app/shadow/models.py`: `Candle` / `Ticker`（mid）/ `Signal` / `VirtualOrder`（never real）/
  `VirtualPosition`（apply_fill / unrealized_pnl）/ `ShadowEvent` / `shadow_safety()`。
- `backend/app/shadow/market_data.py`: `MarketDataClient`(Protocol＝将来の Public adapter 用 interface) /
  `normalize_ticker` / `normalize_candles` / `MockMarketDataClient`（in-memory・offline）。
- `backend/app/shadow/service.py`: `ShadowTrader.step()`（signal→virtual order→position→pnl→safety→event。
  注文送信なし）。
- `backend/app/tests/test_shadow_trading.py`: 正規化 / virtual order が real でない / position・PnL /
  safety フラグ / max_units halt を mock で検証。

> 注: `market_data.py` の mock dict キーは **mock 形状**であり、実 GMO Public API のスキーマではない。
> 実 adapter は公式仕様確認後（Phase 2B）に追加する。

## 7. 次フェーズ候補

- **Phase 2B（実装済み）**: GMO Public API 仕様確認 → Public/read-only adapter
  `app/shadow/gmo_public.py`（`GmoPublicMarketDataClient`、`MarketDataClient` を実装）＋ local CLI
  `scripts/fetch_gmo_public_market_data.py` を追加。base `https://forex-api.coin.z.com/public`、
  `/v1/status`・`/v1/ticker`・`/v1/klines` を GET し内部 Ticker/Candle に正規化。APIキー不要・Private 禁止・
  注文なし・保存なし・本番未公開。仕様メモは [GMO_PUBLIC_API_PLAN.md](GMO_PUBLIC_API_PLAN.md)。
  テストは httpx MockTransport でオフライン（`app/tests/test_gmo_public_adapter.py`）。
- **Phase 2C（実装済み・local-only）**: local shadow run runner を追加。
  `app/shadow/signals.py`（`momentum_signal`＝demo 用・収益性判断ではない）/
  `app/shadow/session.py`（`run_shadow_session`＝candles→signal→ShadowTrader→event→
  `events.jsonl`+`summary.json`+`metadata.json` を `shadow_exports/<run_id>/` に保存）/
  CLI `scripts/run_shadow_session.py`（`--source mock|gmo-public`、`--steps` 上限あり・無限ループなし）。
  `shadow_exports/` は **gitignore（commit 禁止）**。注文なし・Private/APIキー/.env 不要。
  実行手順は [SHADOW_RUNBOOK.md](SHADOW_RUNBOOK.md)。テストは `app/tests/test_shadow_session.py`（offline）。
- **Phase 2D（実装済み・local-only）**: shadow run 集計 CLI。`app/shadow/aggregate.py`
  （load_run_summaries / aggregate_summaries / safety_violations / render_markdown / render_*_csv）＋
  CLI `scripts/summarize_shadow_runs.py`（`--input-root shadow_exports --format markdown|csv --out <dir>`）。
  複数 `summary.json` を合計/by_source・symbol・interval・date でグループ集計し、**safety 違反を検出**
  （違反時 exit code 2）。0件/壊れ summary はスキップ報告。入出力とも `shadow_exports/`（gitignore・commit 禁止）。
  ネットワーク不要・APIキー/.env 不要。手順 [SHADOW_RUNBOOK.md](SHADOW_RUNBOOK.md) §8。
- **Phase 2D-2 / 運用（ガイド整備済み・Day 1〜4実施済み）**: 手動gmo-public run、実行後集計、
  safety violation時の停止、生成物のcommit禁止、よくある失敗への対処を
  [SHADOW_RUNBOOK.md](SHADOW_RUNBOOK.md) に整理。1〜2週間の注文なしログ蓄積後にログ品質と停止条件を確認する。
  reports化、SignalFn変更、自動実行はこのフェーズに含めない。
- **Phase 2D-4（レビュー完了）**: Day 1〜4で平日5-step run、週末`no klines`安全停止、月曜復帰を確認。
  safety violation / broken / haltは0。次は`USD_JPY / M1 / steps 10`を手動・Public・注文なしで限定確認できる。
  BUY / SELL / HOLDとRiskManager / OrderCandidate / Kill switch / 注文ログは設計のみ進めてよい。
  詳細は [PHASE2D4_SHADOW_LOG_REVIEW.md](PHASE2D4_SHADOW_LOG_REVIEW.md)。
- **Phase 2D-5〜2D-7（実施済み）**: `USD_JPY / M1 / steps 10`を3回連続で完了。
  virtual ordersを生成し、safety violation / broken / haltは0を維持。収益性判断には使用しない。
- **Phase 2E-0（設計完了）**: BUY / SELL / HOLD、OrderCandidate、shadow専用RiskManager、Kill switch、
  local監査ログ、安全契約、Phase 2E-1受け入れ条件を定義。
  詳細は [PHASE2E0_SAFETY_DESIGN.md](PHASE2E0_SAFETY_DESIGN.md)。実装は別タスク・明示承認後に限定する。
- **Phase 3**: Private API の **read-only** 設計（残高/建玉の参照のみ。まだ注文なし）。

各フェーズとも、公開 UI / 本番 API への露出と、実注文・実資金・Private API への移行は
[PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) の基準と明示承認のうえで判断する。
