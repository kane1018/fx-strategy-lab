# Shadow Run Runbook（Phase 2C〜2D-2・local-only）

GMO Public（または mock）の相場データで **注文なし**の shadow run をローカル実行し、events/summary を
保存する手順。実注文・実資金・Private API・APIキー・`.env` は使わない。出力 `shadow_exports/` は
**コミット禁止**（gitignore 済み）。設計は [PHASE2_SHADOW_TRADING_PLAN.md](PHASE2_SHADOW_TRADING_PLAN.md)、
Public API 仕様は [GMO_PUBLIC_API_PLAN.md](GMO_PUBLIC_API_PLAN.md)。

## 1. 対象範囲

- local shadow run CLI（mock / gmo-public）、最小 SignalFn、shadow log 保存、summary 集計、offline テスト。
- Phase 2D-2 では、1〜2週間の手動運用でログ品質・継続実行性・safetyを確認する。
- 本番公開なし（`app.main_readonly:app` に追加しない）。注文なし・Private API/APIキー禁止。
- 収益性評価、SignalFn 開発、パラメータ最適化、自動実行、reports/UI公開は行わない。

## 2. 実行前チェック

```bash
cd /Users/naoikansui/Desktop/トレード
git branch --show-current
git status --short
git check-ignore backend/shadow_exports
git ls-files | grep shadow_exports || true
```

- branch と既存差分を把握し、`backend/shadow_exports/` が ignore 対象で、追跡ファイルがないことを確認する。
- gmo-public は認証不要の Public GET のみ。Private API、APIキー、`.env`、注文送信は使わない。
- 出力はローカル限定であり、実 API レスポンスの生データは保存しない。

## 3. mock run（事前・切り分け用）

ネットワークを使わない deterministic run。初回確認、CLI変更後、gmo-public失敗時の切り分けに使う。

```bash
cd /Users/naoikansui/Desktop/トレード/backend

# ヘルプ
python3 -m scripts.run_shadow_session --help

python3 -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 20
```

mockが成功してgmo-publicだけ失敗する場合は、市場時間、日付、Public API、ネットワークを確認する。
Private APIやAPIキーへ進んではならない。

## 4. gmo-public run（手動・1回ずつ）

```bash
cd /Users/naoikansui/Desktop/トレード/backend
python3 -m scripts.run_shadow_session --source gmo-public --symbol USD_JPY \
    --interval M1 --date YYYYMMDD --steps 5
```

- `--date`: UTC基準の `YYYYMMDD`。省略時はUTC当日。取引日の指定を基本とし、未来日や形式違いを避ける。
- `--symbol`: GMO形式の `BASE_QUOTE`。暫定運用は `USD_JPY` を基本とする。
- `--interval`: 内部表記 `M1` / `M5` / `M15` / `M30` / `H1` / `H4` / `D`、または対応する
  GMO表記 `1min` / `5min` / `15min` / `30min` / `1hour` / `4hour` / `1day`。
- `--steps`: 必ず正の上限を指定する。初回は5、通常は5〜50を目安とし、無限実行しない。
- `--units` / `--max-units`: virtual数量と停止閾値。初期値を基本とし、収益最適化に使わない。
- `--out-root`: 既定 `shadow_exports`（=`backend/shadow_exports/`）。別の追跡対象パスへ変更しない。

市場時間、指定日、klines提供状況、rate limit、ネットワークにより失敗しうる。失敗時は原因を記録して
そのrunを終了し、必要ならmockで切り分ける。認証付き経路への切替、APIキー追加、無限retryは禁止。

## 5. 出力ファイル構成

```text
shadow_exports/<run_id>/
  events.jsonl    # 1 step 1 行（signal / virtual_order / position / virtual_pnl / safety ...）
  summary.json    # run 集計（下記）
  metadata.json   # run パラメータ + safety + 注意書き
```

- run_id 例: `YYYYMMDD_HHMMSS_shadow_USD_JPY_mock`。
- **実 API レスポンスの生データは保存しない**（内部正規化済みの event/summary のみ）。

## 6. summary の主項目

run_id / source / symbol / interval / steps_requested / steps_executed / events_count /
virtual_orders_count / buy_count / sell_count / flat_count / max_abs_units /
final_position_side / final_position_units / final_average_price / final_unrealized_pnl /
last_price / data_points / halted / halt_reason / safety / created_at。

## 7. SignalFn について

`app/shadow/signals.py` の `momentum_signal`（last close > prev → buy、< → sell、== → flat）は
**動作確認用の最小シグナルであり、収益性判断のための戦略ではない**。パラメータ最適化や戦略研究はしない。

## 8. 集計とsafety確認

run後は毎回Markdown集計を実行する。数日分をファイル出力する場合も出力先は必ず
`shadow_exports/` 配下に置く。

```bash
cd /Users/naoikansui/Desktop/トレード/backend
python3 -m scripts.summarize_shadow_runs --help
python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format markdown
python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format csv
python3 -m scripts.summarize_shadow_runs --input-root shadow_exports --format csv \
    --out shadow_exports/aggregate
```

集計では合計に加え、source / symbol / interval / date別のrun数、注文なしのvirtual集計、haltを確認できる。
`safety_violation_runs_count` が **0** であり、各summaryのsafetyが次を満たすことを確認する。

- `real_order=false`
- `private_api_used=false`
- `api_key_used=false`
- `no_order_execution=true`
- `live_trading_environment_enabled=false`
- `gmo_order_enabled=false`

1件でもsafety violationがある場合、CLIは警告してexit code 2を返す。その日の運用を直ちに止め、
`safety_violations` のrun_id / field / value / expectedを確認する。該当runを安全扱いに書き換えず、
原因が解消してofflineテストと安全レビューが完了するまでgmo-public runを再開しない。

補足する構造上の制約:

- 各 event/summary に `shadow_safety()`: `real_order=false` / `private_api_used=false` /
  `api_key_used=false` / `no_order_execution=true` / `live_trading_environment_enabled=false` /
  `gmo_readonly=true` / `gmo_order_enabled=false`。
- 注文送信関数なし。`VirtualOrder(real_order=True)` は拒否。`units > max_units` で halt（以降ポジション不変）。
- gmo-public は Public GET のみ・認証ヘッダ無し・Private フォールバックなし・取得失敗は明示エラー。

## 9. よくある失敗と対処

| 症状 | 確認・対処 |
| --- | --- |
| 市場時間外・メンテナンス | そのrunを終了し、取引時間内または既知の取引日で後ほど手動再実行する。mockでCLI自体を確認する。 |
| `--date` 指定ミス | UTC基準の8桁 `YYYYMMDD`、実在する過去または当日の取引日か確認する。 |
| `no klines` | symbol / interval / dateを確認する。データがない日はスキップし、認証付きAPIへ切り替えない。 |
| ticker/kline skew reject | `--enable-shadow-risk`時、現在tickerとBUY/SELL対象klineのtimestamp差が大きい場合はcandidate生成前に`NO_TRADE`へ倒れる。これは安全fail closedであり、skew閾値を安易に緩めない。直近足で再確認する場合も1回ずつ手動で行い、生成物はcommitしない。 |
| interval不正 | `M1/M5/M15/M30/H1/H4/D` または対応するGMO表記を使う。 |
| rate limit（HTTP 429 / `ERR-5003`） | 連続実行を止め、時間を置いて1回だけ手動再実行する。retryループを追加しない。 |
| network timeout / parse error | 接続状況とPublic APIの稼働を確認し、そのrunを終了する。mockでローカル処理を切り分ける。 |
| input root不在 | backendから実行しているか、`shadow_exports/` が存在するか確認する。先にmock runを1回実行する。 |
| safety violation | 直ちに当日の運用を停止し、§8の手順で原因確認・offlineテスト・安全レビューを行う。 |
| `.venv/bin/pytest` が起動しない | 移動前パスの古いshebangが原因なら `python3 -m pytest -q` を使う。`.env`やコードで回避しない。 |

失敗をPrivate API、APIキー、`.env`、実注文で解決しようとしてはならない。

## 10. 1〜2週間の暫定運用ルール

1. 最初は `USD_JPY`、intervalは `M1` または `M5`、stepsは5〜50に固定する。
2. 1日1〜3回、コマンドを人が確認して手動実行する。cron / schedule / 常駐botは使わない。
3. 各run後にsummarizeを実行し、`safety_violation_runs_count=0` とhalt / broken summaryを確認する。
4. 日付・symbol・interval・steps、成功/失敗理由だけを運用メモに残す。secretや生レスポンスは残さない。
5. 出力はローカルの `backend/shadow_exports/` のみに蓄積し、commitもreports/UI公開もしない。
6. 目的は継続動作、ログ品質、集計可能性、安全性の確認であり、PnLを収益性の根拠にしない。
7. safety violationが1件でも出た日、または予期しない出力が出た日はそこで停止する。

### Phase 2E-5 gmo-public risk/audit継続確認

Phase 2E-5で `--enable-shadow-risk` を使うgmo-public risk/audit確認は、上記の暫定運用より狭い条件で行う。

- `source=gmo-public`、`symbol=USD_JPY`、`interval=M1`、`steps=5`、`--enable-shadow-risk`に固定する。
- manual only、1日1回までにする。
- 当日の日付を使い、原則として市場時間中に実行する。
- 各run後にsummary、metadata、signal/candidate/risk/virtual audit logs、aggregateを確認する。
- `REAL_PUBLIC_BID_ASK`、ALLOW、REJECT、virtual result、ticker/kline skew、fetch error、safetyを確認する。
- HOLD中心、ticker/kline skew、spread too wide、ticker stale、fetch error fail closedは保留/追加観察として扱える。
- safety violation、broken summary、invalid risk row、raw response保存、Private API/APIキー/broker/実注文痕跡、
  candidate/decision/virtual result相関不整合、`shadow_exports/`追跡対象混入があれば停止してレビューへ戻る。
- PnLは収益性判断に使わない。
- 詳細は [PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md](PHASE2E5_GMO_PUBLIC_RISK_AUDIT_CONTINUATION_PLAN.md)。

Phase 2E-5 1回目レビューでは、`20260622_103430_shadow_USD_JPY_gmo-public` で
`REAL_PUBLIC_BID_ASK` 2件、ALLOW 1件、`cooldown_active` REJECT 1件、ALLOW時のみvirtual result、
REJECT時virtual resultなしを確認した。同日2回目は1日1回ルールにより実行せず停止した。次回2回目は別日に
1回だけ実行する。詳細は
[PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md](PHASE2E5_RUN1_REVIEW_AND_NEXT_RUN_PREP.md)。

## 11. commit禁止の最終確認

```bash
cd /Users/naoikansui/Desktop/トレード
git status --short
git check-ignore backend/shadow_exports
git ls-files | grep shadow_exports || true
git diff --cached --name-only
```

- `git check-ignore` が `backend/shadow_exports` を示し、`git ls-files` は何も返さないことを確認する。
- `shadow_exports/`、`shadow_exports/aggregate/`、実APIレスポンス、集計CSV/JSON/Markdownはgit addしない。
- 既存のローカル生成物は勝手に削除・移動・編集しない。

## 12. Phase 2D-2の完了判断

- 運用ガイド整備は完了。実運用の完了判断には、1〜2週間の手動ログと日別集計の確認が別途必要。
- 期間中のsafety violation、壊れたsummary、継続的な取得失敗を整理してから停止条件をレビューする。
- 次フェーズへ自動的に進まない。Private API、実資金、実注文、本番公開は必ず別タスク・事前レビューとする。
