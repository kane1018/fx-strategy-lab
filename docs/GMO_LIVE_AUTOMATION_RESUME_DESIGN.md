# GMO FX 実資金自動売買 再開設計（ドラフト・未実装）

本書は Step 6G-PC-OX-R 系インシデント（`live_order_once.py` 等の実POST可能経路と、
Step 6G "controlled/safe" simulation 系の混在）を踏まえ、GMO FX 実資金自動売買を
**将来安全に再開するための設計**をまとめたものである。本書自体はコード実装を含まない。
数値（リスク上限の具体的な金額・数量）は本書では決め切らず、設定項目と判定構造のみを固める。

関連: [`../AGENTS.md`](../AGENTS.md)、[`CODEX_HANDOFF.md`](CODEX_HANDOFF.md)（インシデント記録）、
`backend/app/security/real_broker_post_hard_guard.py`（既存hard guard。当初
`app/live_verification/`にあったが、production broker/service経路との分離のため
`app/security/`へ移設済み）。

## 1. GMO live自動売買再開の必須条件

以下がすべて満たされるまで、GMO実資金自動売買は有効化しない。

1. `GmoFxBroker.market_order()` / official settlement dedicated path が実装・テスト・レビュー済みで、
   `OandaBroker`と同じく `risk_service` / `AutomationRunner` / `bot_service` 経由に統合されている。
2. `backend/app/live_verification/`（Step 6G controlled/simulation系、および `live_order_once.py`）は
   自動売買経路から**一切import/呼び出しされない**ことがテストで固定されている。
3. `real_broker_post_hard_guard.py` の default-deny は維持され、統合後の経路でも実送信直前で
   引き続き呼ばれる（統合＝ガード撤去ではない）。
4. allow bridge（複数booleanから許可を自動算出する再利用可能な判定器）は作らない。
5. `GMO_FX_ORDER_ENABLED` 相当のenable設定は既定OFFで、プロセス再起動後も自動でOFFに戻る。
6. 十分なpaper trade実績（`paper_trade_gmo` / `performance_report`）が存在する。
7. 運営者による明示的な書面上の承認（sign-off）が記録されている。
8. Kill switch・settlement照合ロジックが実装され、synthetic fixtureで全異常系がテスト済み。
9. repo clean、HEAD==origin/main、全テスト green、ruff clean。

## 2. GmoFxBrokerの統合位置

- `backend/app/brokers/gmo_fx_broker.py` の `market_order()`（現状は無条件raise）を実装し、
  `OandaBroker`と同一の `Broker` インターフェースを満たす形にする。
- 署名・認証は `app/private_api/auth.py` の `build_auth_headers`（既存の実装・監査済み）を
  再利用し、`live_order_once.py`内の独自署名ロジックは使わない。
- 決済は専用の official settlement dedicated route を呼ぶ専用メソッド（例:
  `GmoFxBroker.close_position()`）とし、generic opposite order（両建てクローズ）は使わない。
- **アーキテクチャ上の硬い境界**: `gmo_fx_broker.py` は `app.live_verification.*` を
  import しない。これをsource-scanテストで固定する（既存の
  `test_live_verification_real_post_capability_isolation.py` と同じパターン）。
- 統合後も、`market_order()` / `close_position()` の実送信直前で
  `real_broker_post_hard_guard.assert_real_broker_post_allowed(allow=...)` を呼ぶ。
  `allow` は `bot_service`/`AutomationRunner` 側の既存enableチェック（`GMO_FX_ORDER_ENABLED`
  ＋`admin_live_enabled`＋confirmation phrase一致等、OANDAのlive-mode gateと同型）から
  渡される値のみとし、専用の「許可判定器（allow bridge）」は作らない。

## 3. risk_serviceとの接続設計

- `evaluate_order_risk()` の構造はそのまま再利用する。
- 現行の「`mode=="live"`なら無条件で`実資金ブローカーアダプターが未実装`を追加」という
  ブロックは、`GmoFxBroker`実装完了後に、具体的なGMO live gate群（
  `enable_live_trading`、`admin_live_enabled`、confirmation phrase一致、
  `api_connection_ok`、risk config妥当性、**加えてGMO固有の**
  paper実績フラグ・kill switch armedフラグ・settlement route確認済みフラグ）
  へ置き換える。「未実装」という文言のまま実装済みにはしない。
- `bot_service.start_bot()` は、既存の demo/practice以外を`risk_stopped`にする
  二重ガードと同型で、GMO live専用の起動前チェック（下記kill switch条件）を
  start時に一括評価する。

## 4. kill switch条件

| 条件 | 挙動 |
|---|---|
| 起動時 | 必ずOFF（自動復帰しない。プロセス再起動後も同様） |
| manual stop | 最優先。毎サイクルの最初にチェックし、trueなら即停止 |
| stale price | 既存 `_assert_fresh_price` と同型で停止 |
| risk_service rejected | GMO live経路では即bot停止（demo/paperのような「このシグナルだけskip」ではなく停止） |
| settlement rejected | 停止。retry/repostしない |
| settlement unknown/timeout | fail-closedで停止（成功扱いにしない） |
| active/pending order conflict | entry試行前に検出したら停止（自動キャンセルしない） |
| multiple positions検出 | 本来起きないはずの異常として即停止 |
| 連敗上限到達 | 停止 |
| 日次損失上限到達 | 停止 |
| 最大entry回数(`max_entries_per_day`)到達 | 停止 |
| kill switch作動中 | entry・settlementいずれの新規POSTも行わない（単一の`status`フラグで一元管理） |

## 5. 最小RiskConfig案（項目のみ、数値は保留）

既存`RiskConfig`（`max_daily_loss` / `max_loss_per_trade` / `max_positions` /
`max_units` / `max_consecutive_losses` / `max_spread_pips` / `avoid_news_minutes`）に加え、
GMO live専用として以下のフィールドを新設する。数値は次の議論で決める。

- `max_positions`: 1（構造上も1に固定）
- `max_entries_per_day`: 1から開始（候補）
- `max_settlements_per_position`: 1（同一ポジションへの決済試行は1回のみ）
- `max_consecutive_losses`: 2 または 3（比較検討中）
- `order_size_safe_label`: GMOの最小許容単位に固定。引き上げには設定ファイル変更＋
  再デプロイ＋レビューを必須とし、実行時にコードから変更不可にする。
- `official_settlement_route_required`: True（固定・configで変更不可）
- `generic_close_allowed`: False（固定・configで変更不可。テストで固定）

## 6. settlement照合設計

1. official settlement dedicated routeのみを使う（generic opposite order禁止、テストで固定）。
2. settlement POSTがsanitized acceptedを返しても、その場では「決済完了」扱いにしない。
3. 続けてread-onlyのsafe confirmation（openPositions count）を取得し、
   `NO_POSITION`/`count=0`を確認できた時点で初めて「決済完了」とする
   （OANDAの`close_unconfirmed`と同じ思想）。
4. rejected/unknown/timeoutの場合は停止し、retry/repostしない。運営者の手動対応に委ねる。
5. `max_settlements_per_position=1`をポジション単位の状態（DB）でも構造的に強制する
   （risk_serviceのチェックだけに依存しない）。

## 7. Level 5 full auto completed=true の条件

以下の**すべて**が、1つのfresh cycle内でmanual interventionなしに成立した場合のみtrue。

1. entry POSTがちょうど1回実行され、結果がaccepted(sanitized)
2. entry後のread-only確認で`ONE_POSITION_OPEN`/`count=1`を確認
3. official settlement POSTがちょうど1回実行され、結果がaccepted(sanitized)
4. settlement後のread-only確認で`NO_POSITION`/`count=0`を確認
5. retry/repost/second POSTが一度も発生していない
6. manual stop・manual close・manual overrideなどの人手介入が一切なかった
7. kill switchが一度も作動していない

上記のいずれかが未達・不明・timeoutの場合は`Level_5_full_auto_cycle_completed=false`とする
（これはCODEX_HANDOFF.mdの過去記録で既に踏襲されているルールと同じ）。

## 8. no-POSTで先に実装すべきStep一覧

1. 本設計書のリスク上限数値・段階的ロールアウト期間の確定（別途議論）
2. ✅ **完了**: `gmo_fx_broker.py`が`app.live_verification.*`を一切importしないことを固定する
   source-scan/isolationテスト追加（`test_gmo_fx_broker_live_verification_isolation.py`）。
   同Stepで`real_broker_post_hard_guard.py`を`app.security`へ移設済み。
3. ✅ **完了**: `app/private_api/order_builders.py`に、entry注文用・official settlement用の
   pure body/signing-ready request plan builderを追加（実送信なし、`auth.py`は呼ばない設計、
   fake fixtureのみでテスト・`test_private_api_order_builders.py`）。settlementは
   `/private/v1/closeOrder`専用route固定、size-based以外（position-specific）は
   構造上サポートせず明示的に拒否する。
4. ✅ **完了（no-POSTスケルトンのみ）**: `GmoFxBroker.market_order()`をentry専用skeletonとして
   実装。上記builderで作った`GmoFxPrivateRequestPlan`を使い、`real_broker_post_hard_guard`を
   実送信直前に必ず呼ぶ。production側で`allow_real_broker_post`をTrueにする配線は一切なく、
   実HTTP transportも未実装のため常に例外で停止する（`test_gmo_fx_broker_market_order_no_post.py`）。
   settlement・risk_service接続・kill switch・paper実績チェックはこのStepでは未実装。
5. ✅ **完了（no-POSTスケルトンのみ）**: `GmoFxBroker.official_settlement_order()`を
   size-based専用skeletonとして実装。`market_order()`とは別メソッドで、generic opposite orderは
   使わず、entry builderではなく`build_gmo_fx_official_settlement_request_plan`のみを使う。
   settlement side（決済方向）は`entry_side_safe_label`（`ENTRY_BUY`/`ENTRY_SELL`のみ）から
   `derive_settlement_side_from_entry_side_safe_label`で機械的に導出し、side provenanceが
   ready でない限りrequest planを作らずに停止する。導出ルール（entryの反対sideで決済）自体は
   GMO公式closeOrder docsとの整合を人手でまだ確認していないため、
   `settlement_side_official_docs_semantics_confirmed=false`のまま。実送信直前で
   `real_broker_post_hard_guard`を必ず呼び、production側で許可配線はなく、実HTTP transportも
   未実装のため常に例外で停止する（`test_gmo_fx_broker_official_settlement_no_post.py`）。
   position-specific settlement・risk_service接続・kill switch・paper実績チェックは未実装。
6. GMO専用RiskConfigフィールドの追加（構造のみ、保守的な仮数値）
7. `bot_service`/`automation_service`にGMO専用kill switch条件を追加
   （settlement rejected/unknown/timeout、active/pending conflict、multiple positions、
   `max_entries_per_day`、`max_settlements_per_position`）
8. settlement reconciliation（post-settlement read-only確認、close_unconfirmed相当）実装
9. Level 5 full auto completed状態機械の実装。synthetic fixtureで全異常系をテスト
10. fake transportのみを使った統合テスト一式
    （entry accepted→position確認→settlement accepted→NO_POSITION確認=Level5 true、
    および全失敗分岐=Level5 false+bot停止）
11. `live_order_once.py`と Step 6G "controlled" simulation系（約130ファイル）の
    廃止・隔離（自動売買から使われないことを明示するマーカー追加、またはディレクトリ移動）
12. 運営者レビュー・sign-offチェックリスト文書化
13. `GMO_FX_ORDER_ENABLED`を本番で手動ONにする（上記すべて完了後、十分なpaper実績確認後のみ）

## 9. 次に実装する最小Step

**`gmo_fx_broker.py`が`app.live_verification.*`を一切importしないことを固定する
source-scan/isolationテストを追加する。**

理由:
- 新規production codeの追加が一切不要（テストファイル1つのみ）。
- 「Step 6G controlled系・simulation系とは明確に分離する」という最優先原則を、
  実装より先にテストとして固定できる。
- 既存の`test_live_verification_real_post_capability_isolation.py`と同じ設計パターンを
  再利用でき、今後の全GmoFxBroker実装がこの境界を最初から守る形になる。
- 現状の`gmo_fx_broker.py`は既にこの境界を満たしている（`app.brokers.base` /
  `app.config` / `app.schemas.trading` / `app.services.market_data_service` /
  `app.services.risk_service`のみimport）ため、テスト追加は既存動作を壊さない。

## 10. 確認事項

本書作成にあたり、実POST・credential使用・.env読取・raw response/broker response本文・
ID・数量・価格・損益の表示は一切行っていない。コード実装（`.py`ファイルの追加・変更）も
行っていない。本ファイル（`.md`のみ）の新規追加のみ。
