# Phase 2E-0: Shadow candidate / risk / kill switch 安全設計

## 1. 目的と範囲

本書は、GMO Public APIによる注文なしshadow runの次段階として、実資金検証前に必要な安全契約を定義する。
対象はBUY / SELL / HOLD判定、OrderCandidate、shadow専用RiskManager、Kill switch、local監査ログである。

これは**設計文書であり実装ではない**。Private API、APIキー、broker接続、実注文、実資金、本番API/UIを
追加しない。Phase 2E-1の実装は、本書のレビューと明示承認を受けた別タスクに限定する。

## 2. 現在の前提

- Phase 2D-5〜2D-7で `USD_JPY / M1 / steps 10` を3回実行し、すべて10 stepsを完了した。
- 全体集計は11 runs / 100 steps / 86 virtual orders、halted 0、safety violation 0、broken/skipped 0。
- Private API、APIキー、実注文、実資金は使用していない。`shadow_exports/` は未追跡。
- 現在の `momentum_signal` はdemoであり、PnLとcandidate件数を収益性判断に使わない。
- 現在のshadowモデルは `buy / sell / flat` と `VirtualOrder` を持つ。Phase 2E-1では既存挙動を壊さず、
  新しいcandidate/risk境界を別レイヤーとして追加する。
- `app.services.risk_service` は既存のOrderRequest、Settings、live modeに結びつく別機能である。
  Phase 2E-1のshadow RiskManagerからimport・再利用せず、`app/shadow/` 内に閉じる。

## 3. 状態モデルと処理順

シグナルと処理結果を同じenumに混在させない。

- `signal_label`: `BUY | SELL | HOLD`
- `disposition`: `CANDIDATE_CREATED | NO_TRADE | BLOCKED_BY_RISK | VIRTUAL_RESULT | HALTED`
- `reason_code`: `INVALID_DATA` 等の機械可読な理由

処理順は固定する。

1. Public由来データを正規化・検証する。
2. Kill switchがactiveなら`HALTED / KILL_SWITCH_ACTIVE`として終了し、candidateを作らない。
3. データ・市場・時間条件を満たさない場合は`NO_TRADE`として記録し、candidateを作らない。
4. SignalFnが`HOLD`なら状態維持を記録し、candidateを作らない。
5. `BUY / SELL`だけがOrderCandidate生成へ進む。
6. RiskManagerが全条件を評価し、`ALLOW_SHADOW`または`REJECT`を返す。
7. rejectは`BLOCKED_BY_RISK`として記録し、virtual fillへ進めない。
8. allowはshadow上の処理継続だけを許可し、`VirtualOrder` / virtual resultへ進める。
9. 各境界で安全契約を検査し、違反時はKill switchをactiveにしてfail closedする。

## 4. 判定ラベル定義

| 状態 | 意味 | OrderCandidate |
| --- | --- | --- |
| `BUY` | 買い方向のshadow候補。実注文ではない | 他のgateを満たす場合のみ生成 |
| `SELL` | 売り方向のshadow候補。実注文ではない | 他のgateを満たす場合のみ生成 |
| `HOLD` | 既存のvirtual状態を維持する戦略判断 | 生成しない |
| `NO_TRADE` | データ、市場、時間、対応範囲等により候補なし | 生成しない |
| `BLOCKED_BY_RISK` | BUY/SELL候補をRiskManagerが拒否 | candidateは記録するが処理しない |

`HOLD`は正常な戦略判断、`NO_TRADE`はpre-risk gateの結果、`BLOCKED_BY_RISK`はcandidate生成後のrisk結果であり、
意味を相互変換しない。既存の`Signal.side="flat"`はPhase 2E-1境界で`HOLD`へ明示変換する。

補足reason code:

- `INVALID_DATA`: 欠損、非有限値、OHLC不整合、時刻逆転、symbol不一致。
- `MARKET_CLOSED`: Public statusが閉場・メンテナンス。状態不明もallowしない。
- `SPREAD_TOO_WIDE`: 実Public tickerから計算したspreadがpolicy上限超過。
- `RATE_LIMITED`: HTTP 429 / `ERR-5003`。candidateを作らずretry loopもしない。
- `API_ERROR`: timeout、HTTP、parse等のPublic取得失敗。
- `KILL_SWITCH_ACTIVE`: 停止中。原因確認前に処理を再開しない。

コード上のenum memberは大文字、JSONへ保存する値は対応するlower snake caseに統一し、自由記述の文字列を
制御分岐に使用しない。

現在のcandle由来tickerはbid=askのsynthetic zero spreadであるため、これを実spreadとしてrisk通過に使ってはならない。
spread判定を必須化する統合段階ではPublic tickerの正規化値が必要で、不明なspreadはfail closedにする。

## 5. OrderCandidate設計

OrderCandidateは**ローカルshadow処理の入力候補**であり、注文、注文要求、broker order IDではない。

必須項目:

| 項目 | 型・制約 |
| --- | --- |
| `schema_version` | 固定文字列。互換性判定用 |
| `candidate_id` | run内で一意。broker IDとして使用禁止 |
| `run_id` | 親shadow runとの相関ID |
| `timestamp` | timezone付きUTC ISO 8601 |
| `market_data_timestamp` | 判断に用いた最新データ時刻 |
| `source` | `mock`または`gmo-public`。認証source禁止 |
| `symbol` | policyで許可されたsymbol |
| `interval` | policyで許可されたinterval |
| `side` | `BUY`または`SELL`のみ |
| `quantity_mode` | Phase 2E-1は`FIXED_VIRTUAL_UNITS`のみ |
| `quantity` | 正の有限値。policy上限以下 |
| `entry_reference_price` | 正の有限な参照価格。約定価格ではない |
| `spread_pips` | 正規化済みPublic ticker由来。未取得ならnullでrisk reject |
| `signal_name` | SignalFn識別子。demoであることを保持 |
| `signal_reason` | 人間向け理由。機密情報を含めない |
| `confidence` | 任意の0〜1またはnull。現demoではnull、allow根拠にしない |
| `risk_status` | 生成時`PENDING`。RiskDecisionでのみ確定 |
| `blocked_reason` | 生成時null。candidate自体を書き換えずdecision側に記録 |
| `real_order` | `false`固定。`true`を構築不能にする |
| `private_api_used` | `false`固定 |
| `api_key_used` | `false`固定 |
| `created_by` | `shadow_candidate_factory`等の固定識別子 |

設計制約:

- immutableなデータ型とし、`real_order=true`を表現できない型・constructor validationを併用する。
- submit / send / place / cancel / amend / broker変換メソッドを持たない。
- Private API情報、APIキー、secret、account ID、残高、建玉、broker order IDを持たない。
- candidateから既存`OrderRequest`やbroker requestへ変換するadapterを作らない。
- IDと時刻はorchestration境界から注入可能にし、pure/offline testを決定的にする。
- reference priceは正規化Public tickerのBUY=ask / SELL=bidとし、約定保証やfill価格として扱わない。

## 6. Shadow RiskManager設計

RiskManagerは `evaluate(candidate, context, policy) -> RiskDecision` のpure functionとする。ファイル、ネットワーク、
DB、broker、`.env`、グローバル設定を読まない。policyとcontextはimmutableな明示引数で渡す。

RiskDecisionの必須項目:

- `decision_id`, `candidate_id`, `run_id`, `timestamp`
- `outcome`: `ALLOW_SHADOW | REJECT`
- `reason_codes`: reject時は1件以上、allow時は空
- `evaluated_checks`: 実施したcheck名とpass/fail
- `kill_switch_active`, `safety` snapshot

RiskPolicyはallowed symbols/intervals、quantity上限、spread上限、run/UTC日別candidate上限、cooldown、
data freshness、連続API error閾値を持つimmutableな明示引数とする。RiskContextは評価時刻、market status、
Public spread、run/日別件数、重複key、直近candidate時刻、KillSwitchState、安全snapshotを持つ。
policy/contextの欠損・不正値は起動または評価をfail closedにする。

`ALLOW_SHADOW`は**実注文許可ではない**。candidateをvirtual処理へ渡してよい、というローカルshadow上の意味だけを持つ。

reject条件:

- `invalid_data`: 非有限価格、欠損、時刻不整合、stale data、symbol不一致。
- `market_closed`: closed / maintenance / unknown。
- `spread_too_wide`: policy上限超過。spread不明も`missing_required_fields`でreject。
- `max_candidates_per_run_exceeded`: 上限到達後は新規candidateをreject。
- `max_daily_candidates_exceeded`: UTC日付の上限到達。
- `duplicate_candidate`: 同一run・symbol・interval・side・market data timestampの重複。
- `cooldown_active`: 明示policyのcooldown内。
- `kill_switch_active`: active中は常にreject。
- `unsupported_symbol`, `unsupported_interval`: allowlist外。
- `quantity_over_limit`: 0以下、非有限、上限超過を含む。
- `missing_required_fields`: confidence以外の必須項目欠損。
- `safety_flag_violation`: §9の期待値と不一致。
- `unknown_state`: 未知enum、未定義reason、評価不能。既定allowにしない。

全checkを可能な範囲で評価して理由を複数記録する。ただし入力を安全に解釈できない場合は即rejectしてよい。
reject時はvirtual positionを変更しない。不明・例外・policy欠損はfail closedでrejectする。
market/data pre-gateでNO_TRADEにすべき条件もRiskManagerで再検査し、誤ってcandidateが到達してもrejectする。

## 7. Kill switch設計

Kill switchはrun単位のsticky stateとし、`inactive -> active`の一方向だけをPhase 2E-1で実装する。
同一process内の自動復帰、時間経過による復帰、例外握りつぶしを禁止する。

停止条件:

- `safety_violation_detected`
- `private_api_used_detected`
- `api_key_used_detected`
- `real_order_true_detected`
- `unexpected_broker_call_detected`
- `too_many_candidates`
- `repeated_api_errors`（閾値は明示policy。未設定なら起動を拒否）
- `broken_summary_detected`
- `manual_stop_file_exists`
- ログ書き込み失敗、未知状態、未処理例外、安全policy不整合

要件:

- active化と同時にcandidate生成・risk allow・virtual fillを停止する。
- `halt_reason`, `trigger`, `timestamp`, `run_id`, 最後の安全snapshotをローカル監査ログへ残す。
- 停止中の各stepは`HALTED / KILL_SWITCH_ACTIVE`として観測可能にする。
- 再開は原因確認、新しいrun、明示的な手動操作を必要とする。停止runをその場でresumeしない。
- manual stop fileの既定位置は`shadow_exports/STOP`とし、内容をsecretとして利用しない。`.env`で指定しない。
- 実注文を止める装置ではない。Phase 2E-1にはそもそも実注文機能を存在させない。

`unexpected_broker_call_detected`は防御的reason codeである。構造上はbroker objectを依存注入せず、
`app.brokers` / `app.services.risk_service` / `OrderRequest`のimport禁止をstatic/offline testで保証する。
candidate上限への到達は通常のRiskManager rejectとし、内部countが上限を超えている、またはreject後にも
candidate処理が継続した場合を`too_many_candidates`によるKill switch対象とする。

## 8. ログ・監査設計

保存先は`shadow_exports/<run_id>/`のみとし、既存どおりgitignore・commit禁止とする。JSONLは1行1event、
UTF-8、追記型とし、各行に`schema_version`, `event_type`, `run_id`, `timestamp`, 相関IDを持たせる。

| ログ | ファイル例 | 主な内容 |
| --- | --- | --- |
| `signal_decision_log` | `signal_decisions.jsonl` | BUY/SELL/HOLD、NO_TRADE理由、入力データ時刻、SignalFn |
| `candidate_log` | `candidates.jsonl` | OrderCandidateの全非機密項目 |
| `risk_decision_log` | `risk_decisions.jsonl` | allow/reject、全reason、評価check、safety、kill state |
| `virtual_result_log` | `virtual_results.jsonl` | candidate/decision相関ID、virtual fill/position/PnL、halt状態 |
| `kill_switch_log` | `kill_switch.jsonl` | active化理由、trigger、時刻、安全snapshot |

規則:

- HOLD / NO_TRADEもsignal decisionへ記録し、「ログがないため不明」を避ける。
- BUY/SELLはcandidate logとrisk decision logを1:1で相関できるようにする。
- REJECTにはvirtual resultを作らない。必要なら`blocked` eventをrisk decisionに含める。
- ALLOW_SHADOW後のvirtual resultはcandidate_idとdecision_idを必須にする。
- ログ書き込み失敗は成功扱いにせずKill switchをactiveにする。部分成功をsummaryで隠さない。
- 生APIレスポンス、認証header、secret、APIキー、account ID、個人情報を保存しない。
- 本番UI、reports API、`analysis_exports`、DBへ接続しない。

## 9. 安全契約

candidate、risk decision、virtual result、summaryの各境界で次を検証する。

```text
real_order=false
private_api_used=false
api_key_used=false
no_order_execution=true
live_trading_environment_enabled=false
gmo_order_enabled=false
```

1項目でも欠損または不一致ならsafety violationである。candidateを処理せず、Kill switchをactiveにし、
CLIは非0で終了する。欠損を`false`相当とみなさない。`gmo_readonly=true`もmetadataとして維持する。

## 10. Phase 2E-1で実装してよい最小範囲

- `app/shadow/`内の判定label / disposition / reason code型。
- immutableなOrderCandidate、RiskPolicy、RiskContext、RiskDecision、KillSwitchState型。
- brokerを呼ばないcandidate factoryとpure RiskManager。
- HOLD / NO_TRADE / BLOCKED_BY_RISKの分岐。
- sticky・fail-closedなlocal Kill switch。
- §8のlocal JSONLログと既存summaryへの件数・安全項目の最小拡張。
- mock/offline unit tests、parser/境界test、既存shadow regression test。
- summarizeがcandidate/reject/halt/safety件数を読める最小拡張。

Phase 2E-1もlocal-only / no-order / no-Private / no-keyとし、既存`app.main_readonly:app`、frontend、broker、
DB、既存live向けRiskManagerを変更しない。実装ファイルとtestの具体的な許可範囲は次タスクで改めて限定する。

## 11. まだ進まない範囲

- Private API、APIキー、`.env`依存、secret。
- 残高、建玉、注文履歴、約定の取得。
- 実注文、注文変更、注文取消、実資金、自動売買。
- GMO/OANDA Private client、LiveBroker、broker adapter/変換。
- cron、schedule、常駐bot、通知。
- 本番API追加、frontend公開、reports接続。
- DB本番化、認証、Render/Vercel設定変更。
- M5、他通貨、ロット可変、ナンピン、マーチンゲール。

## 12. Phase 2E-1受け入れ条件

- `real_order=true`を型・constructor・testのすべてで拒否する。
- submit / send / place / cancel / amend等のbroker送信関数がshadow packageに存在しない。
- `app.brokers`、Private API、既存`app.services.risk_service`、`OrderRequest`をimportしない。
- `.env`を読まず、APIキー・secret・account IDを型やログで扱わない。
- HOLD / NO_TRADEではcandidateが0件、BUY/SELLでは条件を満たす場合だけ1件生成される。
- 全candidateに1件のRiskDecisionがあり、reject理由は必ず1件以上記録される。
- unknown/missing/exceptionはallowされず、必要条件ではKill switchがactiveになる。
- Kill switch active中はcandidate生成、ALLOW_SHADOW、virtual fillがすべて0件になる。
- safety violationが1件でもあれば停止・非0終了し、summaryへ違反を記録する。
- log書き込み失敗を成功扱いにしない。
- mock/offline testsで全reject条件、kill条件、ログ相関、既存shadow回帰を検証できる。
- `shadow_exports/`は未追跡で、生APIレスポンスを保存しない。
- backend公開API、frontend、DB、認証、外部設定の差分がない。

## 13. ChatGPTへの引き継ぎ要約

Phase 2E-1は、`app/shadow/`に閉じたlocal-only安全レイヤーの最小実装として切り出す。
シグナル`BUY/SELL/HOLD`と処理結果`NO_TRADE/BLOCKED_BY_RISK`を分離し、immutable OrderCandidate、
pure RiskManager、sticky Kill switch、相関可能なlocal JSONLログ、offline testsだけを対象にする。
ALLOW_SHADOWはvirtual処理継続の意味に限定し、broker、Private API、APIキー、実注文、本番API/UIへ接続しない。
実装前に本書のfield、reason code、policy値、停止・再開手順をレビューし、許可ファイルを明示すること。
