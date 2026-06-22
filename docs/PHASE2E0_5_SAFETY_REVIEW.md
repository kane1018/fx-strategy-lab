# Phase 2E-0.5: Shadow safety policy review

## 1. 目的と適用範囲

本書は、Phase 2E-1の最小実装前に、Phase 2E-0で未確定だったRiskPolicy、reason code、識別子、
JSONL schema、停止・手動再開手順を確定する規範文書である。実装、テスト追加、Private API、APIキー、
実注文、実資金、本番API/UI変更は対象外とする。

[PHASE2E0_SAFETY_DESIGN.md](PHASE2E0_SAFETY_DESIGN.md) と本書が競合する場合、Phase 2E-1の
shadow safety policyには本書を優先する。値の変更はdocsレビューと明示承認を経てschemaまたはpolicy versionを
更新し、実装だけを先行させない。

## 2. 現在の前提

- Phase 2D-5〜2D-7の `USD_JPY / M1 / steps 10` は3回とも完了した。
- 現在の集計はruns 11、steps 100、virtual orders 86、halted 0、safety violation 0、broken/skipped 0である。
- Private API、APIキー、実注文、実資金は未使用で、PnLを収益性判断に使わない。
- Phase 2E-0でOrderCandidate、pure RiskManager、sticky/fail-closed Kill switch、安全契約を設計済みである。
- 既存live向け `app.services.risk_service` はimport・再利用しない。
- Phase 2E-1の安全レイヤーは `app/shadow/` に閉じ、`ALLOW_SHADOW` はvirtual処理継続だけを意味する。
- 現在のcandle由来bid/askはsynthetic zero spreadであり、実spreadとしてriskを通過させない。

## 3. RiskPolicy初期値

Phase 2E-1のpolicy identifierは `shadow-risk-policy-v1` とし、初期値を次で固定する。

```text
allowed_symbols = ["USD_JPY"]
allowed_intervals = ["M1"]
max_candidates_per_run = 10
max_daily_candidates = 30
max_quantity = 100
quantity_mode = "fixed"
max_spread_pips = 0.5
max_data_age_seconds = 180
max_future_skew_seconds = 5
cooldown_seconds = 60
max_consecutive_api_errors = 3
max_log_write_failures = 0
allow_synthetic_zero_spread = false
allow_private_api = false
allow_api_key = false
allow_real_order = false
allow_broker_call = false
```

- `max_quantity=100` はvirtual candidateの将来の最小単位検証を意識した上限であり、注文数量ではない。
- `quantity_mode` は文字列 `fixed` だけを許可する。既存設計上の表示名 `FIXED_VIRTUAL_UNITS` は
  serializer境界で `fixed` に正規化し、別modeを黙って変換しない。
- すべての上限はinclusiveである。candidate 10件目、UTC日内30件目、quantity 100、spread 0.5 pips、
  data age 180秒は許可対象となり、それを超えた値をrejectする。
- safety booleanは設定で緩和できない固定契約である。policy読込値と固定契約が違えばKill switchをactiveにする。
- `.env`、APIキー、broker/account状態をpolicy sourceにしない。初期値はコード内immutable valueまたは明示引数で渡す。

### 3.1 data freshness

- timestampはtimezone-aware UTCへ正規化し、`data_age = evaluation_time_utc - market_data_timestamp_utc` で判定する。
- `0 <= data_age <= 180 seconds` のときだけfreshとする。180秒超は `stale_data` でrejectする。
- 未来時刻は5秒までclock skewとして許容し、5秒超は `invalid_data` とする。
- timestamp欠損、timezone不明、parse不能、非有限値は `invalid_data` とする。ローカル時刻へ暗黙変換しない。
- 一つのstepでは評価開始時の `evaluation_time_utc` を固定し、処理途中の時計変化で判定を変えない。

### 3.2 spread

- Phase 2E-1はUSD_JPYだけを対象とし、1 pipを `0.01 JPY` と固定する。
- 実Public bid/askがともに有限、正、かつ `ask >= bid` の場合だけ、
  `spread_pips = (ask - bid) / 0.01` で計算する。
- `spread_pips <= 0.5` は許可対象、0.5超は `spread_too_wide` でrejectする。
- candle closeから作ったbid=askなど、出所がsyntheticのzero spreadは
  `synthetic_spread_not_allowed` でrejectする。数値が0であることだけでsyntheticとは判定せず、provenanceを必須にする。
- bid/askまたはprovenance欠損、ask < bid、非有限値は `invalid_data` とする。

### 3.3 candidate count、duplicate、cooldown

- run countとdaily countは生成されたすべての一意なOrderCandidateを数える。RiskManagerでrejectされたcandidateも含み、
  HOLD / NO_TRADEと重複として生成を拒否した試行は含めない。
- run countはrun_id単位、daily countはcandidateのmarket data timestampをUTC日に正規化した
  `[00:00:00, next 00:00:00)` 単位で、同じlocal `shadow_exports/` 内の全runを合算する。
- daily countを確定できない、または集計状態が壊れている場合は `unknown_state` としてfail closedにする。
- 重複keyは `(run_id, step_index, symbol, interval, side, signal_name, market_data_timestamp)` とする。
  同一keyの2件目は `duplicate_candidate` でrejectする。
- cooldownは同一 `symbol + side` で直前に生成されたcandidateのmarket data timestampとの差を使う。
  60秒未満を `cooldown_active` でrejectし、60秒以上を許可対象とする。時系列逆転は `invalid_data` とする。

### 3.4 API error、log failure、CLI終了

- API errorは一つのCLI run attempt内のGMO Public取得エラーを数える。成功レスポンスで0にresetし、
  no-klinesやinvalid payloadもerror 1回として扱う。Private APIによるfallbackは行わない。
- 3回連続した時点で `repeated_api_errors` によりKill switchをactiveにする。Phase 2E-1で自動retryは追加せず、
  retryを将来追加する場合もこの同じcounterを通す。
- `max_log_write_failures=0` のため、必須JSONLまたはsummaryの最初の書込み・flush・close・atomic replace失敗で
  `log_write_failed` として即時停止する。書けなかったkill eventはstderrにも最小情報を出す。
- CLI exit codeは `0=正常完了`、`1=通常の入力/Public取得/no-klines失敗`、
  `2=safety violation/Kill switch/log integrity failure` とする。既存summarizerのsafety exit 2と合わせる。

## 4. reject reason code

reject時は次のsnake_case codeを1件以上、決定論的な順序の配列で記録する。未知codeを受け入れず、
判定不能は `unknown_state` としてfail closedにする。

| code | 人間向け説明 |
|---|---|
| `invalid_data` | 値、timestamp、bid/ask、時系列などが無効 |
| `market_closed` | 市場閉場または取引対象時間外 |
| `stale_data` | data ageが180秒を超過 |
| `spread_too_wide` | 実spreadが0.5 pipsを超過 |
| `synthetic_spread_not_allowed` | synthetic zero spreadをrisk入力に使用 |
| `max_candidates_per_run_exceeded` | run内candidateが10件を超過 |
| `max_daily_candidates_exceeded` | UTC日内candidateが30件を超過 |
| `duplicate_candidate` | 定義済みduplicate keyが既存candidateと一致 |
| `cooldown_active` | 同一symbol/sideの前candidateから60秒未満 |
| `kill_switch_active` | sticky Kill switchがすでにactive |
| `unsupported_symbol` | `USD_JPY` 以外 |
| `unsupported_interval` | `M1` 以外 |
| `quantity_over_limit` | virtual quantityが100を超過 |
| `quantity_mode_not_allowed` | quantity modeが `fixed` でない |
| `missing_required_fields` | candidate/risk入力の必須field欠損 |
| `safety_flag_violation` | 固定safety contractの欠損または不一致 |
| `log_write_failed` | 必須監査ログの永続化失敗 |
| `unknown_state` | 既知codeへ安全に分類できない状態 |

同時に複数条件へ該当した場合はすべて記録する。ただしKill switch条件が成立した後は追加のallow評価やvirtual fillを行わない。

## 5. Kill switch reason code

| code | 発火条件 |
|---|---|
| `safety_violation_detected` | safety contractの一般違反を検出 |
| `private_api_used_detected` | Private API使用を示す値・経路を検出 |
| `api_key_used_detected` | APIキー使用を示す値・経路を検出 |
| `real_order_true_detected` | `real_order=true` を検出 |
| `unexpected_broker_call_detected` | broker送信・注文経路への到達を検出 |
| `too_many_candidates` | 上限reject後も生成継続、または保存状態が上限を超過 |
| `repeated_api_errors` | Public取得エラーが3回連続 |
| `broken_summary_detected` | 必須summaryが破損または整合しない |
| `manual_stop_file_exists` | 規定STOPファイルが存在 |
| `log_write_failed` | 必須ログを1回でも確実に保存できない |
| `policy_mismatch` | policy identifier/固定値/実装期待値が不一致 |
| `unknown_exception` | 未分類例外を捕捉 |
| `unknown_state` | 安全に分類・継続できない状態 |

通常の10件/30件上限到達後の新candidateはrisk rejectである。上限reject後にもcandidate生成・allow・virtual fillが
続いた場合、または読込済み状態がすでに上限超過なら `too_many_candidates` を発火する。

Kill switch active時はcandidate生成、risk allow、virtual fill、Public再取得を停止する。同一run内ではstickyで、
時間経過、成功レスポンス、STOP削除による自動復帰をしない。原因確認後、新しいrun_idでのみ手動再開する。

## 6. candidate_id / decision_id

```text
candidate_id = cand_<run_id>_<step_index>_<side>_<short_hash>
decision_id = risk_<candidate_id>_<short_hash>
```

- `step_index` はrun内0始まりの整数で、入力market dataの安定した処理順に採番する。skipしても再利用しない。
- candidate hash対象は `run_id, step_index, symbol, interval, side, signal_name,
  market_data_timestamp, entry_reference_price` とする。
- timestampはUTCのRFC 3339（microseconds、`Z`）、priceは指数表記を使わない正規化decimal文字列へ変換する。
- field名昇順、UTF-8、空白なしのcanonical JSONをSHA-256へ入力し、先頭12文字のlowercase hexを `short_hash` とする。
- decision hash対象は `candidate_id, policy_id=shadow-risk-policy-v1` とし、同じcanonicalizationを使う。
- candidateとRiskDecisionは1対1とする。同じcandidateの再評価は `duplicate_candidate`、同一IDでpayloadが違う場合は
  `policy_mismatch` または `unknown_state` で停止する。
- timestampだけに依存せず、APIキー、secret、account情報、生APIレスポンスをIDやhash対象に含めない。

## 7. JSONL schema version

初期versionは次で固定する。

```text
schema_version = "shadow-risk-v1"
```

対象eventは `signal_decision_log`、`candidate_log`、`risk_decision_log`、`virtual_result_log`、
`kill_switch_log` とする。すべての行に最低限 `schema_version`, `event_type`, `run_id`, `timestamp` を持たせ、
関連する行には `candidate_id` / `decision_id` を持たせる。秘密情報、生APIレスポンス、account ID、broker order IDは持たせない。

- 新versionでschema_version欠損、未知version、必須field欠損があれば安全上不完全としてrejectまたは停止する。
- field削除、意味変更、型変更は破壊的変更としてversionを上げる。optional field追加は同versionでもよいがdocsとtestを更新する。
- JSONLはlocal `shadow_exports/<run_id>/` のみへ保存し、Git、reports、frontend、DB、analysis_exportsへ接続しない。
- 既存Phase 2C/2Dログはlegacyとして読める状態を保つ。summarizerは既存Markdown/CSV fieldを変更・削除せず、
  `risk_pipeline` countsとreason breakdownを追加する。legacy summaryに新fieldがないことだけでbrokenとせず、
  `schema_version=shadow-risk-v1` を名乗る新runの欠損だけをbroken/safety対象にする。

## 8. manual stop file運用

既定パスはrepository root基準で `backend/shadow_exports/STOP` とする。CLIはPublic network取得前、各step開始前、
candidate生成前、virtual fill前に存在確認し、見つけた時点で `manual_stop_file_exists` を記録して停止する。

作成:

```bash
cd /Users/naoikansui/Desktop/トレード/backend
mkdir -p shadow_exports
touch shadow_exports/STOP
```

確認:

```bash
test -f shadow_exports/STOP && echo "STOP active"
```

解除:

```bash
rm shadow_exports/STOP
```

- STOPは空でよく、`.env`に依存しない。`shadow_exports/`とともにGit管理対象外とする。
- 削除は対象process停止、kill log確認、原因確認、安全契約再確認の後にoperatorが手動で行う。
- STOP削除後も停止済みprocess/runをresumeしない。新しいrun_idの新processだけを開始する。
- STOPの検出・解除で既存ログを削除、上書き、commitしない。

## 9. 停止後の手動再開手順

1. 対象run/processを停止し、exit codeを記録する。
2. `kill_switch_log` とstderrを確認し、reason codeと最初の発火点を特定する。
3. summary/metadataのsafety snapshotを確認し、壊れたログを削除・修復して成功扱いにしない。
4. `real_order=false`, `private_api_used=false`, `api_key_used=false`, `no_order_execution=true`,
   `live_trading_environment_enabled=false`, `gmo_order_enabled=false` を確認する。
5. STOPがある場合は作成理由を確認し、原因解消と確認記録の後に手動削除する。
6. `git check-ignore backend/shadow_exports` と `git ls-files` で生成物がGit管理対象外であることを確認する。
7. 必要な場合だけ、STOP解除後にmock/offline runでCLI健全性を確認する。Private API/APIキーへfallbackしない。
8. 停止runを再利用せず、新しいrun_idで手動runを開始する。
9. summarizeを実行し、broken/skipped、halt、reason別件数を確認する。
10. 新runのsafety violationが0であることを確認する。0でなければ再停止し、同じ手順を繰り返す。

自動復帰、time-based reset、daemon/cronによる再起動、失敗runの途中再開は禁止する。

## 10. Phase 2E-1で触ってよいファイル候補

最終的なPhase 2E-1指示で、必要なファイルだけを再度列挙して確定する。候補範囲は次に限定する。

```text
backend/app/shadow/**
backend/app/tests/test_shadow_*.py
backend/app/tests/shadow/**
backend/scripts/run_shadow_session.py
backend/scripts/summarize_shadow_runs.py
docs/PROJECT_STATUS.md
docs/CODEX_HANDOFF.md
docs/PHASE2_SHADOW_TRADING_PLAN.md
docs/PHASE2E0_SAFETY_DESIGN.md
docs/PHASE2E0_5_SAFETY_REVIEW.md
```

現在のtest配置は主に `backend/app/tests/test_shadow_*.py` である。新しいsubdirectoryを採用するかはPhase 2E-1の
具体的なfile manifestで決める。上記globは一括変更許可ではなく、candidate/risk/kill/log/summaryとoffline testに
必要な最小ファイルだけを対象とする。

## 11. Phase 2E-1でまだ触らない範囲

```text
backend/app/main.py
backend/app/main_readonly.py
frontend/**
backend公開API
Render / Vercel設定
.env
.env.example
GMO Private API
OANDA Private API
backend/app/brokers/**
backend/app/services/risk_service.py
broker / live trading関連
OrderRequestおよび注文系API
DB / 認証
reports公開
```

残高、建玉、注文履歴、約定、実注文、注文変更、注文取消、実資金、自動売買、cron、常駐bot、M5、他通貨も対象外である。

## 12. Phase 2E-1受け入れ条件

- `real_order=true`, `private_api_used=true`, `api_key_used=true` を型・constructor・parserで拒否する。
- broker送信関数がなく、`app.brokers`、既存live RiskManager、OrderRequest、Private clientをimportしない。
- `.env`を読まず、APIキー、secret、account ID、broker order IDを型・hash・ログで扱わない。
- OrderCandidateをOrderRequestへ変換する経路がない。
- §3のpolicy値、境界、UTC日界、duplicate/cooldown/API error定義を実装し、offline境界testを持つ。
- RiskDecisionのrejectには§4のreasonが1件以上あり、unknown/missingはfail closedになる。
- Kill switch active時はcandidate生成、risk allow、Public再取得、virtual fillが停止し、同一runで復帰しない。
- log write失敗は最初の1回で停止・exit 2となり、成功summaryとして扱わない。
- §6のIDが決定論的でcandidate/decisionを1対1に相関できる。
- すべての新JSONL行が `shadow-risk-v1` と正しいevent_typeを持つ。
- summarizeでcandidate/reject/kill switch/safety、reason breakdownを確認でき、legacy出力との後方互換性を保つ。
- mock/offline testsで全reject/kill条件、STOP、ログ相関、既存shadow回帰を検証できる。
- backend/frontendの公開面、DB、認証、外部設定に差分がない。
- `shadow_exports/`が未追跡で、生APIレスポンスやaggregate実データをcommitしない。

## 13. Phase 2E-1実装前レビュー結果

当初の未決事項は本書で次のように確定した。

| 項目 | 決定 |
|---|---|
| spread単位/pips変換 | USD_JPYは0.01 JPY/pip、実bid/askのみ |
| step_index | run内0始まり、処理順、再利用なし |
| candidate重複範囲 | §3.3の7-field key |
| daily count日付境界 | market timestampのUTC日、全local runを合算 |
| API error count | CLI run attempt内の連続Public取得失敗、成功でreset、3回でkill |
| log失敗時exit code | safety failureとして2 |
| summarize拡張 | 既存field維持、`risk_pipeline` counts/reason breakdown追加 |
| 後方互換性 | legacy欠損は許容、新schemaを名乗る欠損はbroken/safety対象 |

Phase 2E-1開始前に残る作業は、実装promptで具体的な変更file manifestを確定し、本書のpolicyを事前レビューすることだけである。
安全policy上の未決値を実装者判断で補わない。

## 14. ChatGPTへの引き継ぎ要約

Phase 2E-1は `shadow-risk-policy-v1` と `shadow-risk-v1` を実装するlocal-onlyタスクとして切り出す。
対象は `USD_JPY / M1`、fixed virtual quantity、pure RiskManager、deterministic ID、sticky Kill switch、
local JSONL、offline tests、後方互換なsummarize拡張に限定する。STOPはPublic取得前からfail closedで確認し、
停止runは復帰させず、新run_idで手動再開する。既存live RiskManager、broker、Private API、APIキー、実注文、
本番API/UI、DB、認証には接続しない。実装依頼では変更fileを候補範囲からさらに限定し、本書の全受け入れ条件を検証する。
