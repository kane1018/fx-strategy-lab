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
- **Phase 2E-0.5（設計レビュー完了）**: RiskPolicy初期値、reject/kill reason code、data/spread/count境界、
  deterministic ID、`shadow-risk-v1`、manual STOP、手動再開手順、Phase 2E-1許可範囲を確定。
  詳細は [PHASE2E0_5_SAFETY_REVIEW.md](PHASE2E0_5_SAFETY_REVIEW.md)。当該フェーズでは実装なし。
- **Phase 2E-1（local-only安全基盤実装済み）**: immutable OrderCandidate、RiskPolicy/RiskDecision、
  pure risk評価、sticky KillSwitchState、broker非接続candidate factory、fail-closed JSONL writer、
  legacy互換のrisk集計とoffline testsを追加。既存sessionへの統合は行わず、本番API/UIにも公開しない。
- **Phase 2E-1.5（監査完了・D判定）**: import/local-only境界とlegacy互換は確認したが、provenance、
  malformed policy、audit event schema/output root、unsafe risk row検出に統合前必須修正あり。
  [PHASE2E1_SAFETY_AUDIT.md](PHASE2E1_SAFETY_AUDIT.md) のD-1〜D-4を修正・再監査するまでPhase 2E-2は禁止。
- **Phase 2E-1H（corrective hardening完了・local-only）**: D-1〜D-4に対し、spread provenance enumの
  fail closed化、RiskPolicy/RiskContext/KillSwitchState invariant、malformed evaluate境界、typed audit schema、
  trusted root配下JSONL writer、summarizerのunsafe/correlation violation検出、adversarial offline testsを追加。
  既存shadow sessionへは未統合で、本番API/UI、Private API、APIキー、実注文には接続していない。
  再監査は **B判定**。統合前必須修正はなくPhase 2E-2の設計着手は可。ただしPhase 2E-2実装は、
  KillSwitchStateのsession ownership、監査ログ失敗時exit 2、session統合境界とintegration testの設計レビュー、
  明示承認まで進まない。詳細は [PHASE2E1H_REAUDIT.md](PHASE2E1H_REAUDIT.md)。
- **Phase 2E-2（session統合前の安全接続設計完了）**: 既存shadow sessionへhardening済みlocal-only安全基盤を
  どう接続するかを設計した。run単位のKillSwitchState所有、run/Public取得/step/candidate/risk/virtual fill前の
  pre-gate、AuditLogWriteError時のkill switch activeとexit code 2、STOPファイル、candidate/decision/virtual result
  相関、risk JSONLとlegacy summary互換、Phase 2E-2実装で触ってよい範囲と触らない範囲、integration testと
  受け入れ条件を整理した。今回は設計のみで、`run_shadow_session.py`や`app/shadow/`コードは変更していない。
  実装は別タスク・明示承認後に限定する。詳細は
  [PHASE2E2_SESSION_INTEGRATION_DESIGN.md](PHASE2E2_SESSION_INTEGRATION_DESIGN.md)。
- **Phase 2E-2（local-only risk/audit最小統合完了）**: `--enable-shadow-risk`の明示フラグ時だけ、既存shadow
  sessionへSTOP pre-gate、run単位KillSwitchState、BUY/SELL candidate、pure risk evaluate、typed audit JSONL、
  REJECT時virtual result抑止、AuditLogWriteError時fail closed/exit code 2、summary/metadata risk fieldsを接続した。
  デフォルトrunはlegacy互換を維持し、risk logなしrunは従来どおり集計できる。mockのkline-only経路では
  synthetic spreadとしてrisk rejectに倒し、明示bid/askがある場合のみALLOWとvirtual_result_log相関を許す。
  本番API/UI、Private API、APIキー、broker、実注文には接続していない。
- **Phase 2E-2.5（session統合監査完了・B判定）**: Phase 2E-2実装結果をレビューし、default legacy互換、
  `--enable-shadow-risk`限定有効化、STOP/audit failure時exit code 2、synthetic spread reject、explicit bid/ask allow、
  REJECT時virtual resultなし、candidate/decision/virtual result相関、summarize互換、Private API/broker/OrderRequest/
  `.env`未接続を確認した。修正必須事項はなく、次はPhase 2E-3設計に進める。詳細は
  [PHASE2E2_INTEGRATION_AUDIT.md](PHASE2E2_INTEGRATION_AUDIT.md)。
- **Phase 2E-3（Public ticker bid/ask provenance連携実装完了・local-only）**: GMO Public `/v1/ticker`由来bid/askを
  `--enable-shadow-risk`経路へ安全に渡すため、`REAL_PUBLIC_BID_ASK`付与条件、kline-only synthetic reject維持、
  timestamp/freshness/skew/spread検証、MarketSnapshot、raw response非保存、session no-network責務分離、
  fail closed、audit/summary metadata、offline testsを実装した。valid Public tickerのみALLOW候補へ進み、
  missing/invalid/stale/future/skew tickerはcandidateなしのNO_TRADEまたはrisk rejectに倒す。今回もGMO Public実run、
  Private API、APIキー、broker、実注文、本番公開API追加は行っていない。
  詳細は [PHASE2E3_PUBLIC_TICKER_BID_ASK_DESIGN.md](PHASE2E3_PUBLIC_TICKER_BID_ASK_DESIGN.md)。
- **Phase 2E-3.5（Public ticker bid/ask provenance連携監査完了・B判定）**: Phase 2E-3実装をレビューし、
  Public ticker由来bid/askの厳格な`REAL_PUBLIC_BID_ASK`付与、kline-only synthetic reject維持、
  invalid/missing/stale/future/skew tickerのfail closed、raw response非保存、summary/metadata後方互換、
  Private API / APIキー / broker / OrderRequest / `.env`未接続を確認した。修正必須事項はなく、次は
  Phase 2E-4設計または実行指示作成へ進める。詳細は
  [PHASE2E3_PUBLIC_TICKER_BID_ASK_AUDIT.md](PHASE2E3_PUBLIC_TICKER_BID_ASK_AUDIT.md)。
- **Phase 2E-4 / 2E-4.5（gmo-public risk/audit手動確認・結果レビュー完了）**:
  `USD_JPY / M1 / steps 5 / --enable-shadow-risk` を1回だけ実行し、exit code 0、haltなし、safety violation 0、
  raw response保存なし、Private API/APIキー/broker/実注文なしを確認した。BUY/SELLの2 stepは
  `ticker_kline_skew_reject_count=2` によりcandidate生成前の`NO_TRADE`へ倒れたため、実runでの
  `REAL_PUBLIC_BID_ASK` candidate/ALLOW/virtual result相関は未確認。レビューでは安全fail closedと判定し、
  次は当日・直近klineでの1回限定再確認を第一候補とした。詳細は
  [PHASE2E4_GMO_PUBLIC_RISK_AUDIT_REVIEW.md](PHASE2E4_GMO_PUBLIC_RISK_AUDIT_REVIEW.md)。
- **Phase 2E-4R（REAL_PUBLIC_BID_ASK実run確認レビュー完了）**:
  直近kline条件でgmo-public risk/auditを1回だけ再確認し、`REAL_PUBLIC_BID_ASK` candidate 1件、
  `ALLOW_SHADOW` 1件、対応するvirtual result 1件、candidate/decision/virtual result相関を確認した。
  古い3 stepはticker/kline skewで安全に`NO_TRADE`へ倒れ、safety violation / broken / raw response保存 /
  Private API / APIキー / broker / 実注文はなし。これによりPhase 2E-5設計へ進めるが、実装・Private API・
  実注文へは進まない。詳細は
  [PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md](PHASE2E4R_GMO_PUBLIC_REAL_BID_ASK_REVIEW.md)。
- **Phase 2E-5（gmo-public risk/audit継続確認計画 設計完了）**:
  今後のPublic risk/audit runを、manual only、`USD_JPY / M1 / steps 5 / --enable-shadow-risk`、
  1日1回まで、短期3回・中期5〜10回を目安に継続確認する計画を定義した。成功条件、保留条件、
  停止条件、ticker/kline skew評価、評価指標、Phase 2Fへ進む条件を整理した。Phase 2FはPrivate APIではなく
  Public shadow risk/auditのレビュー・安定性評価・運用計画として扱う。今回もgmo-public再実行、コード変更、
  Private API、APIキー、broker、実注文には進んでいない。詳細は
  [PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md](PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md)。
- **Phase 3**: Private API の **read-only** 設計（残高/建玉の参照のみ。まだ注文なし）。

各フェーズとも、公開 UI / 本番 API への露出と、実注文・実資金・Private API への移行は
[PUBLICATION_POLICY.md](PUBLICATION_POLICY.md) の基準と明示承認のうえで判断する。
