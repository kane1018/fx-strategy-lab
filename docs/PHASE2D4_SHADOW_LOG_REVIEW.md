# Phase 2D-4: Day 1〜4 shadow logレビュー

GMO Public APIを使ったlocal-only・注文なしshadow運用のDay 1〜4をレビューし、次に進める範囲を定める。
本書は2026-06-22時点の判断であり、収益性評価、実装、Private API、APIキー、実注文を含まない。

## 1. レビュー対象

運用条件は `USD_JPY / M1 / steps 5`。手動実行のみで、出力はgitignore済みの
`backend/shadow_exports/` に保存した。

| 日 | 日付 | 結果 | 評価 |
| --- | --- | --- | --- |
| Day 1 | 2026-06-18 | 成功、5 steps、2 virtual orders、haltなし | 平日run成功 |
| Day 2 | 2026-06-19 | 成功、5 steps、4 virtual orders、haltなし | 平日run成功 |
| Day 3 | 2026-06-20 | `no klines`、run/summary未生成 | 週末に安全停止 |
| Day 4 | 2026-06-22 | 成功、5 steps、4 virtual orders、haltなし | 月曜に正常復帰 |

Day 1開始前のPhase 2D-2確認runとmock runも同じローカルrootに残っているため、全体集計は
Day 1〜4だけの件数ではない。Day 1〜4の判断は上表の運用記録と該当summaryを基準にする。

## 2. 全体集計

`python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown` の結果:

- runs_count: 8（gmo-public 4 / mock 4）
- symbols: `EUR_JPY`, `USD_JPY`
- intervals: `M1`
- total_steps_executed: 70
- total_virtual_orders_count: 60
- halted_runs_count: 0
- safety_violation_runs_count: 0
- broken/skipped: 0
- Safety Violations: none
- by_date:
  - 2026-06-17: 1 run / 19 virtual orders
  - 2026-06-18: 5 runs / 33 virtual orders
  - 2026-06-19: 1 run / 4 virtual orders
  - 2026-06-22: 1 run / 4 virtual orders

PnLはdemo SignalFnと短いrunによる仮想値であり、収益性判断には使用しない。

## 3. 運用評価

- 3回の平日運用runはすべて指定5 stepsを完了し、virtual orderを生成してhaltなしで終了した。
- 土曜日はklines取得段階で明示エラーとなり、不完全なrun_idやsummaryを作らず安全に停止した。
- 週末失敗後も既存summaryの集計は壊れず、月曜日にPublic klines取得とrun保存が正常復帰した。
- 全summaryで `real_order=false`、`private_api_used=false`、`api_key_used=false`、
  `no_order_execution=true`、`live_trading_environment_enabled=false`、`gmo_order_enabled=false` を維持した。
- `backend/shadow_exports/` はignore対象で、追跡ファイルはない。

したがって、**短時間・小規模・手動のPublic shadow運用基盤は次の限定的検証へ進める程度に安定**している。
一方、日数と件数は少なく、長期安定性、収益性、実注文安全性を示す証拠ではない。

## 4. 次フェーズ判断

| 判断 | 結論 | 条件・理由 |
| --- | --- | --- |
| A. `USD_JPY / M1 / steps 5` 継続 | 継続する | 比較用baselineとして残し、日次safety確認を続ける |
| B. `USD_JPY / M1 / steps 10` | 進めてよい | 手動・1日1回・Public・注文なしで1変数だけ拡張し、毎回summarizeする |
| C. `USD_JPY / M5` | いったん保留 | steps 10と同時に変えず、steps 10を数回確認後に別タスクで判断する |
| D. BUY / SELL / HOLD整理 | 設計へ進めてよい | 表示・型・ログ定義のみ。HOLDは非注文で、実行経路を持たせない |
| E. 安全基盤 | 設計へ進めてよい | RiskManager / OrderCandidate / Kill switch / 注文ログの要件・offline test設計のみ |
| F. Private API / 実注文 | 進まない | APIキー、実資金、自動売買を含め、明示承認と別フェーズが必要 |

steps 10でsafety violation、broken summary、予期しないhalt、取得後の不完全出力が1件でもあれば停止し、
steps 5へ戻して原因をレビューする。steps 10の結果を収益性比較には使わない。

## 5. Phase 2E-0で設計してよい安全基盤

実装前に、次の契約と受け入れ条件をdocsとoffline testsの計画として定義する。

- **BUY / SELL / HOLD**: 判定時刻、symbol、根拠、入力データ範囲を持つ。HOLDはOrderCandidateを作らない。
- **OrderCandidate**: virtual候補であり、`real_order=false`を変更不能にする。broker送信関数を持たない。
- **RiskManager**: candidateをallow/rejectする純粋判定。数量上限、データ鮮度、halt状態、安全フラグを検査し、
  reject理由を必ず記録する。allowも注文許可ではなくshadow処理継続の意味に限定する。
- **Kill switch**: safety不一致、上限超過、データ異常、未処理例外でfail closedに停止する。
  自動復帰せず、原因確認後の明示的な手動再開を前提とする。
- **注文ログ**: 実注文ログではなくcandidate / risk decision / virtual resultのlocal監査ログとする。
  secret、生APIレスポンス、個人情報を含めず、gitignore対象にする。
- **境界テスト**: offline・mockのみ。Private/broker/注文モジュールをimportせず、本番API/UIへ公開しないことを検証する。

Phase 2E-0はまず設計レビューに限定する。RiskManager等の実装は、その設計が承認された別タスクでのみ行う。

## 6. まだ進まないもの

- Private API、APIキー、`.env`、secret。
- 実注文、実資金、自動売買、注文変更・取消。
- broker接続、LiveBroker、残高・建玉・注文・約定取得。
- cron、schedule、常駐bot、通知、DB本番化、認証。
- 本番公開API、frontend/reportsへのshadow結果公開、Render/Vercel設定変更。
- ロット可変、ナンピン、マーチンゲール、複数通貨の実資金化。

## 7. 次タスク

次の1タスクは **`USD_JPY / M1 / steps 10` の手動Public shadow run** とし、baselineのsteps 5は残す。
Phase 2E-0を扱う場合は、上記安全基盤の設計文書作成・レビューだけを別タスクとして依頼する。
どちらも自動的には開始しない。
