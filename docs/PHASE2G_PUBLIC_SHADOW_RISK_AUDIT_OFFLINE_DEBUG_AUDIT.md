# Phase 2G: Public shadow risk/audit オフライン最終デバッグ監査

Phase 2Gでは、Phase 3B Private API read-onlyの公式仕様確認・実装設計へ進む前に、既存の
Public shadow risk/auditの安全境界をオフラインで最終確認する。

今回は **監査・docs化のみ** である。gmo-public再実行、コード修正、テスト追加、Private API接続、
APIキー入力・表示・保存、`.env`表示・変更、`.env.example`変更、broker、注文API、実注文、実資金、
自動売買、本番公開API追加、frontend変更には進まない。

## 1. 目的

- Private API / APIキーを扱う前に、Public shadow risk/auditのSTOP、kill switch、audit failure、
  safety violation、duplicate、cooldown、candidate/decision/virtual result相関を確認する。
- 既存テスト、既存offline mock run、既存summarizeで安全境界が壊れていないことを確認する。
- `shadow_exports/`、raw response、secret、実データがgit管理に混入しないことを確認する。
- Phase 3Bへ進む場合も、対象をread-only公式仕様確認・実装設計に限定する根拠を整理する。

## 2. 前提

Phase 2E-5短期3runとPhase 2Fレビューにより、次を確認済みである。

- 3回すべてで `REAL_PUBLIC_BID_ASK`、candidate、`ALLOW_SHADOW`、ALLOW時のみvirtual resultを確認済み。
- 1回目と3回目で `cooldown_active` による `REJECT_SHADOW` と、REJECT時virtual resultなしを確認済み。
- ticker/kline skewは `stale_data` / `NO_TRADE` へ安全fail closedした。
- safety violation、broken/skipped、invalid risk row、kill switch active、raw response保存は0。
- Private API、APIキー、broker、実注文、実資金は未使用。

## 3. 監査範囲

監査対象:

- `backend/scripts/run_shadow_session.py`
- `backend/scripts/summarize_shadow_runs.py`
- `backend/app/shadow/session.py`
- `backend/app/shadow/risk.py`
- `backend/app/shadow/audit.py`
- `backend/app/shadow/gmo_public.py`
- `backend/app/shadow/aggregate.py`
- shadow / risk / audit / aggregate / gmo / session 関連テスト
- Phase 2E-5 / Phase 2F / Phase 3A 関連docs
- `shadow_exports/` のgit管理境界

対象外:

- gmo-public再実行
- Private API接続
- APIキー入力・表示・保存
- `.env` / `.env.example`変更
- broker / 注文API / 実注文 / 実資金
- backend公開API / `main_readonly.py` / frontend変更
- DB本番化 / 認証 / cron / schedule / 常駐bot

## 4. 実行した確認

### Git / 生成物境界

- 作業ディレクトリ: `/Users/naoikansui/Desktop/トレード`
- branch: `main`
- 作業前HEAD: `47667d485c77d603635ec18fc69a7373a5cde776`
- 作業前 `git status --short --branch`: `## main...origin/main`
- `git check-ignore backend/shadow_exports`: `backend/shadow_exports`
- `git ls-files backend/shadow_exports`: trackingなし
- `git ls-files analysis_exports`: trackingなし

### 既存テスト / lint

```text
python3 -m pytest -q
354 passed in 8.66s

ruff check .
All checks passed!

python3 -m pytest -q app/tests -k "shadow or risk or audit or aggregate or gmo or session"
177 passed, 177 deselected in 3.25s
```

### offline mock run

gmo-publicは再実行せず、既存のlocal mock sourceで1回だけoffline確認した。

```text
python3 -m scripts.run_shadow_session --source mock --symbol USD_JPY --interval M1 --steps 5 --enable-shadow-risk
```

結果:

```text
run_id: 20260624_005528_shadow_USD_JPY_mock
source: mock
symbol: USD_JPY
interval: M1
steps_executed: 5
halted: false
exit_code: 0
candidate_count: 4
risk_allow_count: 0
risk_reject_count: 4
virtual_orders_count: 0
kill_switch_count: 0
kill_switch_active: false
invalid_risk_row_count: 0
audit_log_write_error_count: 0
safety_violation_count: 0
raw_response_saved: false
private_api_used: false
api_key_used: false
```

mock sourceでは `SYNTHETIC_ZERO` spreadがriskでrejectされ、virtual resultへ進まなかった。これは
`synthetic_spread_not_allowed` のfail closedとして期待どおりである。

### summarize確認

mock run後のaggregate確認:

```text
runs_count: 26
broken/skipped: 0
safety_violation_runs_count: 0
invalid_risk_row_count: 0
candidate_count: 30
risk_allow_count: 4
risk_reject_count: 26
virtual_result_count: 4
kill_switch_count: 0
kill_switch_active_runs_count: 0
ticker_bid_ask_used_count: 6
real_public_bid_ask_count: 6
synthetic_spread_reject_count: 16
ticker_kline_skew_reject_count: 12
public_ticker_fetch_error_count: 0
spread_too_wide_count: 0
```

## 5. STOP / kill switch監査

確認結果:

- STOP pre-gateはrun開始前に `shadow_exports/STOP` を検出すると、kill switchを有効化し、
  `exit_code=2`、`halted=true` で停止する。
- step loop中のSTOP確認でも、candidate生成やvirtual result生成へ進む前にkill switchを有効化する。
- kill switch有効時は `can_process_virtual_result()` がfalseになり、virtual resultへ進まない。
- `kill_switch_log.jsonl` が必要な状況ではtyped audit logとして記録される。
- 既存テストでSTOP pre-gate、kill switch、exit code 2が確認されている。

判定:

- STOP / kill switchはfail closedとして機能している。
- Phase 3B前ブロッカーはない。

## 6. audit failure監査

確認結果:

- audit writerはrun root / run dir / event fileのroot containmentを確認する。
- typed JSONL schemaを検証し、イベント種別と必須フィールドを確認する。
- 書き込み後にflush / fsyncを行う。
- required audit writeで `AuditLogWriteError` が発生した場合、sessionはkill switchを有効化し、
  `exit_code=2` で停止する。
- audit failure時にvirtual resultへ進む経路は既存テストで防がれている。
- aggregateはinvalid JSON / schema不整合を `invalid_risk_row_count` と safety violationとして検出する。

判定:

- audit failureは安全停止へ倒れる。
- Phase 3B前ブロッカーはない。

## 7. safety violation監査

確認結果:

- `RiskPolicy` は既定でPrivate API、APIキー、real order、broker call、synthetic zero spreadを許可しない。
- `MarketSnapshot` / `create_public_market_snapshot()` は、`source=gmo-public`、`REAL_PUBLIC_BID_ASK`、
  raw responseなし、Private API/APIキーなしを前提に検証する。
- unsafe provenance、missing/invalid bid/ask、stale/future ticker、ticker/kline skewはfail closedになる。
- session summary / metadataには `real_order=false`、`private_api_used=false`、`api_key_used=false`、
  `no_order_execution=true`、`live_trading_environment_enabled=false`、`gmo_order_enabled=false` が記録される。
- summarize結果でも `safety_violation_runs_count=0`、`invalid_risk_row_count=0` を確認した。

判定:

- Public shadow risk/auditのsafety契約は維持されている。
- Phase 3B前ブロッカーはない。

## 8. duplicate / cooldown監査

確認結果:

- risk評価はduplicate candidate、duplicate decision、duplicate virtual resultを許容しない。
- aggregateはcandidateなしdecision、decisionなしcandidate、candidateごとのdecision数不整合、
  candidate/decisionのrun_idまたはstep不整合、ALLOWでないdecisionへのvirtual resultを検出する。
- `cooldown_active` は既存実runでREJECT理由として観測済みであり、REJECT時virtual resultなしが維持されている。
- offline mock runでは `synthetic_spread_not_allowed` が全candidateに入り、steps 2-4では
  `cooldown_active` も併記された。ALLOWは0で、virtual resultは0だった。

判定:

- duplicate / cooldown / REJECT時virtual result抑止は想定どおり。
- Phase 3B前ブロッカーはない。

## 9. candidate / decision / virtual result相関監査

確認結果:

- candidate生成後、risk decisionがrequired audit logとして記録される。
- `REJECT_SHADOW` の場合は `_event_without_order` に進み、virtual resultを生成しない。
- `ALLOW_SHADOW` かつkill switch inactiveの場合のみvirtual resultへ進む。
- aggregateはvirtual resultが対応するALLOW decisionとcandidate_idを持つ場合のみ有効として数える。
- Phase 2E-5短期3runではALLOW時のみvirtual resultを確認済み。
- offline mock runではrisk allow 0のためvirtual result 0であり、REJECT時抑止を再確認した。

判定:

- candidate / decision / virtual result相関は維持されている。
- Phase 3B前ブロッカーはない。

## 10. run_id衝突監査

確認結果:

- sessionのdefault run_idは秒精度の `YYYYMMDD_HHMMSS_shadow_{symbol}_{source}` である。
- run directory作成は `mkdir(parents=True, exist_ok=True)` であり、同一秒・同一symbol・同一source・同一out-rootで
  並列または連続実行すると、同じrun directoryを再利用する余地がある。
- 現在のPhase 2E-5 / Phase 2F / Phase 2Gはmanual onlyで、1日1回や1回限定の運用であるため、
  実害は確認されていない。

判定:

- **非ブロッカーの残課題** とする。
- Phase 3B read-only公式仕様確認・実装設計へ進む妨げではない。
- ただし、将来のautomation、parallel run、常駐bot、または同一out-rootでの連続実行を扱う前に、
  microseconds / unique suffix / 既存run_dir時fail closedのいずれかを検討する。

## 11. ticker / kline / spread fail closed監査

確認結果:

- Public ticker fetch errorはPrivate APIやAPIキーへfallbackしない。
- ticker missing / invalid / stale / future / kline skewはcandidate生成前またはrisk評価でfail closedになる。
- kline-onlyやmockのsynthetic spreadは `synthetic_spread_not_allowed` でrejectされる。
- `spread_too_wide` はREJECT扱いであり、virtual resultへ進まない。
- Phase 2E-5短期3runでticker/kline skewは `NO_TRADE` へ安全fail closedした。
- summarizeで `public_ticker_fetch_error_count=0` を確認した。

判定:

- ticker / kline / spreadの安全制約は維持されている。
- skew閾値緩和は不要であり、現時点では非推奨のまま。

## 12. aggregate / summarize互換監査

確認結果:

- legacy summaryとrisk/audit summaryの混在に対応している。
- broken summaryはskippedとして扱い、件数に出る。
- invalid risk rowは `invalid_risk_row_count` とsafety violationとして検出される。
- duplicate、相関不整合、REJECTへのvirtual resultを検出できる。
- Public ticker系optional countは、存在するsummaryからaggregateされる。
- mock run追加後もsummarizeは正常に完了し、`broken/skipped=0` を維持した。

判定:

- summarize互換は維持されている。
- Phase 3B前ブロッカーはない。

## 13. Private API / broker / order混入監査

確認結果:

- `backend/app/shadow`、`backend/scripts/run_shadow_session.py`、
  `backend/scripts/summarize_shadow_runs.py` の狭い範囲では、実際のbroker import、注文送信、`.env`読込、
  `os.environ` / `getenv` によるcredential取得は確認されなかった。
- `backend/app/shadow` 内の `private_api`、`api_key`、`secret` などの一致は、固定falseのsafety flag、
  forbidden field名、docstring、コメントであり、credential素材ではない。
- 広い `backend/scripts` / `backend/app/tests` 検索では、既存のbroker系テストや研究用スクリプトに
  OANDA practice / GMO broker関連の参照がある。これらは今回のPublic shadow risk/audit実行経路ではない。

判定:

- Phase 2G対象経路にPrivate API / broker / order混入は確認されない。
- 既存の研究用・別系統テスト参照は今回のブロッカーではない。

## 14. raw response / secret / 実データ監査

確認結果:

- mock runのsummary / metadataで `raw_response_saved=false`。
- `shadow_exports/` はgitignore対象であり、trackingなし。
- `analysis_exports/` のtrackingなし。
- `.env`、`.env.example` は変更していない。
- APIキー、secret、Private情報、実APIレスポンスを表示・保存・commitしていない。

判定:

- raw response / secret / 実データの混入は確認されない。

## 15. ローカル検証環境メモ

- `python3 -m pytest` と `ruff check .` で検証した。
- backend全体テストは354件成功した。
- focused testは177件成功した。
- `.venv/bin/pytest` のshebang差分などに依存せず、Python module実行で安定して確認した。

## 16. ブロッカー判定

判定: **A: Phase 3B read-only公式仕様確認・実装設計へ進んでよい**

理由:

- backend全体テストとlintが成功した。
- shadow / risk / audit / aggregate / gmo / session focused testが成功した。
- offline mock runでsynthetic spreadをREJECTし、virtual resultへ進まないことを確認した。
- summarize互換は維持され、broken / safety violation / invalid risk rowは0だった。
- STOP / kill switch / audit failure / safety violation / duplicate / cooldown / 相関検出の設計と既存テストを確認した。
- Phase 2G対象経路にPrivate API / APIキー / broker / 実注文混入は確認されなかった。
- raw response保存なし、`shadow_exports/` trackingなしを確認した。

ただし、これはPhase 3Bの実装開始承認ではない。次に進む場合も、まず
**Private API read-only公式仕様確認・実装設計** を別タスクで行う。

## 17. 残課題

- default run_idが秒精度で、同一秒・同一symbol・同一source・同一out-rootの並列/連続実行時にrun directoryを
  再利用する余地がある。
- 現在のmanual only運用では非ブロッカーだが、automation、parallel run、cron、常駐bot、Phase 3Bのlocal CLIで
  同一out-rootへの連続実行を扱う前に、unique run_idまたは既存run_dir検出のfail closedを検討する。
- Phase 3Bへ進む前に、公式仕様上のread-only endpointと禁止endpointを確認し、注文系methodを実装範囲から除外する必要がある。

## 18. 次に進める範囲

進めてよい候補:

- Phase 3B read-only公式仕様確認。
- Phase 3B read-only実装設計。
- APIキー / secret管理手順の設計レビュー。
- read-only endpoint / 禁止endpointの整理。
- 注文系endpoint、broker、OrderRequest変換を範囲外に固定する設計docs。

まだ進まない範囲:

- Private API接続。
- APIキー入力・表示・保存。
- `.env`表示・変更。
- broker。
- 注文API。
- 実注文。
- 実資金。
- 自動売買。
- Live Verification Mode実装。
- 本番公開API追加。
- frontend変更。
- DB本番化。
- 認証。
- M5や他通貨への拡張。
- cron / schedule / 常駐bot。

## 19. 変更していない重要箇所

- backendコード: 変更なし。
- backend公開API: 変更なし。
- `backend/app/main_readonly.py`: 変更なし。
- frontend: 変更なし。
- Render / Vercel: 変更なし。
- `.env` / `.env.example` / secret: 変更なし。
- Private API: 未接続。
- APIキー: 未入力・未表示・未保存。
- broker: 未使用・未変更。
- 実注文系: 未使用・未変更。
- `shadow_exports/` / 実データ: commitしない。

## 20. 結論

Phase 2G Public shadow risk/auditオフライン最終デバッグ監査では、既存Public shadow risk/auditの安全境界が
Phase 3B前の確認として十分維持されていることを確認した。

最終判定は **A: Phase 3B read-only公式仕様確認・実装設計へ進んでよい**。

ただし、Phase 3Bで扱うのはread-only公式仕様確認と実装設計に限定し、Private API接続、APIキー入力、
broker、注文API、実注文、実資金、自動売買には引き続き進まない。

## 21. Phase 3B-0追記

Phase 3B-0 Private API read-only公式仕様確認・実装設計は完了済みである。

- GMOコイン外国為替FXの公式API docsを確認した。
- REST GETのread-only候補と、POSTの注文・変更・取消・決済系禁止endpointを整理した。
- 認証・署名、APIキー / secret管理、Phase 3B分割案をdocs-onlyで整理した。
- Private API接続、APIキー入力、`.env`変更、backend実装、broker、注文API、実注文、実資金には進んでいない。
- 詳細は [PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md](PHASE3B0_PRIVATE_API_READONLY_OFFICIAL_SPEC_DESIGN.md)。
